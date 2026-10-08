"""Run bounded, source-only novelty controls through isolated model hosts."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from run_eval import bank, binding, evaluate, export_requests, import_responses, load, write_new


def host_capture(runner, *, prompt, output_schema, model_revision, timeout_seconds):
    scripts = Path(__file__).resolve().parents[2] / 'skills/cnki-paper/scripts'
    sys.path.insert(0, str(scripts))
    if runner == 'codex':
        from avereth_core.hosts.codex import run_codex_exec_isolated
        return run_codex_exec_isolated(prompt=prompt, output_schema=output_schema,
                                      model_revision=model_revision, timeout_seconds=timeout_seconds)
    if runner == 'claude':
        from avereth_core.hosts.claude import run_claude_exec_isolated
        return run_claude_exec_isolated(prompt=prompt, output_schema=output_schema,
                                       model_revision=model_revision, timeout_seconds=timeout_seconds)
    raise ValueError('runner must be codex or claude')


def run_live(cases_path, annotations_path, output_root, *, model, family, runner='codex',
             case_ids=None, max_cases=4, max_calls=8, timeout_seconds=180, capture_fn=host_capture,
             secondary_model=None, secondary_family=None, secondary_runner=None):
    if not model or not family or runner not in {'codex', 'claude'}:
        raise ValueError('an explicit available model, family and supported runner are required')
    if type(max_cases) is not int or not 1 <= max_cases <= 60:
        raise ValueError('max_cases must be from 1 to 60')
    if type(max_calls) is not int or not 2 <= max_calls <= 120:
        raise ValueError('max_calls must be from 2 to 120')
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 600:
        raise ValueError('timeout_seconds must be from 1 to 600')
    if any((secondary_model, secondary_family, secondary_runner)):
        if not secondary_model or not secondary_family or secondary_runner not in {'codex', 'claude'}:
            raise ValueError('secondary model, family and runner must be supplied together')
        if secondary_family.casefold() == family.casefold() or secondary_model == model:
            raise ValueError('secondary must use a different model family')
    bank(Path(cases_path))
    reference = load(annotations_path)
    if (reference.get('schema_version') != 'avereth-novelty-reference/v1' or
            reference.get('cases_sha256') != binding(cases_path)['sha256']):
        raise ValueError('automatic references must bind the current case bank before execution')
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    request_path = output_root / 'requests.json'
    requests = export_requests(Path(cases_path), request_path, case_ids=case_ids, max_cases=max_cases)
    required_calls = len(requests['requests'])
    plan = {'schema_version': 'avereth-novelty-live-plan/v1', 'runner': runner, 'model': model,
            'model_family': family, 'max_calls': max_calls, 'required_calls': required_calls,
            'timeout_seconds': timeout_seconds, 'selected_ids': requests['selected_ids'],
            'requests': binding(request_path), 'annotations': binding(annotations_path),
            'secondary': {'model': secondary_model, 'model_family': secondary_family, 'runner': secondary_runner},
            'input_scope': 'exported candidate claims and source snippets; no reference labels or workflow instructions',
            'scientific_state_modified': False, 'automatic_promotion': False}
    write_new(output_root / 'plan.json', plan)
    if required_calls > max_calls:
        result = {'status': 'NOT RUN', 'reason': 'complete paired orders exceed the declared call budget',
                  'attempted_calls': 0, 'required_calls': required_calls, 'selected_ids': requests['selected_ids']}
        write_new(output_root / 'result.json', result)
        return result
    responses = {'schema_version': 'avereth-novelty-responses/v1', 'run_id': str(uuid.uuid4()),
                 'model': model, 'model_family': family, 'synthetic': capture_fn is not host_capture, 'captures': []}
    attempts = []
    for ordinal, request in enumerate(requests['requests'], 1):
        attempt = {'request_id': request['request_id'], 'request_sha256': request['request_sha256']}
        attempts.append(attempt)
        try:
            captured = capture_fn(runner, prompt=request['prompt'], output_schema=request['output_schema'],
                                  model_revision=model, timeout_seconds=timeout_seconds)
            raw_path = output_root / f'capture-{ordinal:03d}.raw'
            with raw_path.open('xb') as stream:
                stream.write(captured.raw_output)
            metadata_path = output_root / f'capture-{ordinal:03d}-metadata.json'
            write_new(metadata_path, {'context_id': captured.context_id, 'model': captured.model_revision,
                                     'request_sha256': request['request_sha256'], 'host_run_id': captured.run_id,
                                     'raw_output': {**binding(raw_path), 'path': raw_path.name},
                                     'telemetry': captured.telemetry.to_dict() if captured.telemetry else None})
            attempt['raw_capture'] = {**binding(metadata_path), 'path': metadata_path.name}
            raw = captured.raw_output.decode('utf-8')
            response = json.loads(raw)
            trace = {'context_id': captured.context_id, 'model': captured.model_revision,
                     'request_sha256': request['request_sha256'], 'raw_output': raw,
                     'host_run_id': captured.run_id,
                     'telemetry': captured.telemetry.to_dict() if captured.telemetry else None}
            trace_path = output_root / f'capture-{ordinal:03d}.json'
            write_new(trace_path, trace)
            trace_binding = {**binding(trace_path), 'path': trace_path.name}
            responses['captures'].append({**attempt, 'context_id': captured.context_id,
                                          'model': captured.model_revision, 'response': response, 'trace': trace_binding})
            attempt['status'] = 'captured'
            attempt['trace'] = trace_binding
        except (ValueError, OSError, UnicodeError, KeyboardInterrupt) as exc:
            attempt.update(status='failed', error=str(exc) or type(exc).__name__)
            write_new(output_root / f'failure-{ordinal:03d}.json', attempt)
            break
        finally:
            print(json.dumps({'attempt': ordinal, **attempt}, ensure_ascii=False), flush=True)
    responses['failures'] = [row for row in attempts if row['status'] == 'failed']
    responses_path = output_root / 'responses.json'
    write_new(responses_path, responses)
    prediction_path = output_root / 'predictions.json'
    evaluation_path = None
    evaluation_error = None
    cascade = {'status': 'not configured', 'attempted_calls': 0}
    try:
        import_responses(request_path, responses_path, prediction_path)
        report = evaluate(Path(cases_path), Path(annotations_path), prediction_path)
        write_new(output_root / 'primary-evaluation.json', report)
        difficult = [row['id'] for row in report['cases'] if row['predicted_class'] is None]
        eligible = [row['id'] for row in report['cases'] if row['secondary_eligible']]
        if secondary_model:
            remaining = max_calls - len(attempts)
            chosen = eligible[:remaining // 2] if not responses['failures'] else []
            cascade = {'status': 'not required' if not eligible else 'budget exhausted or primary failed',
                       'difficult_ids': difficult, 'selected_ids': chosen,
                       'ineligible': [{'id': row['id'], 'reason': row['secondary_reason']}
                                      for row in report['cases'] if row['id'] in difficult and not row['secondary_eligible']],
                       'not_started_ids': [item for item in difficult if item not in chosen], 'attempted_calls': 0}
            if chosen:
                secondary = run_live(cases_path, annotations_path, output_root / 'secondary',
                                     model=secondary_model, family=secondary_family, runner=secondary_runner,
                                     case_ids=chosen, max_cases=len(chosen), max_calls=remaining,
                                     timeout_seconds=timeout_seconds, capture_fn=capture_fn)
                cascade.update(status=secondary['status'], attempted_calls=secondary['attempted_calls'],
                               result=binding(output_root / 'secondary/result.json'))
                secondary_path = output_root / 'secondary/predictions.json'
                if secondary_path.exists() and secondary.get('evaluation_error') is None:
                    report = evaluate(Path(cases_path), Path(annotations_path), prediction_path,
                                      secondary_predictions=secondary_path)
        evaluation_path = output_root / 'evaluation.json'
        write_new(evaluation_path, report)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        evaluation_error = str(exc)
    result = {'schema_version': 'avereth-novelty-live-result/v1',
              'status': 'COMPLETED' if (len(responses['captures']) == required_calls and not evaluation_error
                                       and cascade['status'] not in {'INCOMPLETE', 'NOT RUN'}) else 'INCOMPLETE',
              'attempted_calls': len(attempts) + cascade['attempted_calls'], 'primary_attempted_calls': len(attempts),
              'captured_calls': len(responses['captures']),
              'required_calls': required_calls, 'selected_ids': requests['selected_ids'],
              'not_started_request_ids': [row['request_id'] for row in requests['requests'][len(attempts):]],
              'attempts': attempts, 'evaluation': binding(evaluation_path) if evaluation_path and evaluation_path.exists() else None,
              'evaluation_error': evaluation_error, 'cascade': cascade,
              'comparison_performed': False, 'absolute_novelty_proven': False, 'automatic_promotion': False}
    write_new(output_root / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cases', type=Path)
    parser.add_argument('annotations', type=Path)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--runner', choices=('codex', 'claude'), default='codex')
    parser.add_argument('--model', required=True)
    parser.add_argument('--family', required=True)
    parser.add_argument('--case-ids', help='comma-separated selected case IDs')
    parser.add_argument('--max-cases', type=int, default=4)
    parser.add_argument('--max-calls', type=int, default=8)
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--secondary-model')
    parser.add_argument('--secondary-family')
    parser.add_argument('--secondary-runner', choices=('codex', 'claude'))
    args = parser.parse_args()
    try:
        result = run_live(args.cases, args.annotations, args.output_root, model=args.model, family=args.family,
                          runner=args.runner, case_ids=args.case_ids.split(',') if args.case_ids else None,
                          max_cases=args.max_cases, max_calls=args.max_calls, timeout_seconds=args.timeout,
                          secondary_model=args.secondary_model, secondary_family=args.secondary_family,
                          secondary_runner=args.secondary_runner)
        print(json.dumps({key: result.get(key) for key in ('status', 'attempted_calls', 'captured_calls', 'required_calls')}))
        return 0 if result['status'] == 'COMPLETED' else 2
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('NOT RUN or incomplete: ' + str(exc))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
