// Build a Chinese academic paper .docx (real footnotes) from content.json.
// Usage: node build_docx.js <content.json> <output.docx>
// Requires: npm install docx  (run inside any build dir)
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, LevelFormat,
  FootnoteReferenceRun,
} = require("docx");

const FN = "\ue000", B_ON = "\ue001", B_OFF = "\ue002";
const Q_ZH_OPEN = "\ue010", Q_ZH_CLOSE = "\ue011";
const Q_EN_OPEN = "\ue012", Q_EN_CLOSE = "\ue013";
const QUOTE_MARKERS = new Map([
  [Q_ZH_OPEN, { text: "“", locale: "zh" }],
  [Q_ZH_CLOSE, { text: "”", locale: "zh" }],
  [Q_EN_OPEN, { text: "“", locale: "en" }],
  [Q_EN_CLOSE, { text: "”", locale: "en" }],
]);
const OPEN_TO_CLOSE = new Map([["“", "”"], ["‘", "’"]]);
const CLOSE_TO_OPEN = new Map([["”", "“"], ["’", "‘"]]);
const bodyFont = { ascii: "Times New Roman", hAnsi: "Times New Roman", eastAsia: "SimSun" };
const headFont = { ascii: "Times New Roman", hAnsi: "Times New Roman", eastAsia: "SimHei" };

function isHan(char) {
  return /[\u3400-\u9fff\uf900-\ufaff]/u.test(char || "");
}

function isLatin(char) {
  return /[A-Za-z]/u.test(char || "");
}

function dominantLocale(text) {
  let cjk = 0;
  let latin = 0;
  for (const char of text) {
    if (isHan(char)) cjk += 1;
    else if (isLatin(char)) latin += 1;
  }
  const strong = cjk + latin;
  if (!strong) return null;
  if (cjk && cjk / strong >= 0.70) return "zh";
  if (latin && latin / strong >= 0.70) return "en";
  return null;
}

function isApostrophe(text, index) {
  if (text[index] !== "’") return false;
  const previous = index ? text[index - 1] : "";
  const following = index + 1 < text.length ? text[index + 1] : "";
  if (isLatin(previous) && isLatin(following)) return true;
  if (isLatin(previous) && (!following || /[\s,.;:!?\])}”]/u.test(following))) return true;
  return /^(?:\d{2}|\d{4})s\b/iu.test(text.slice(index + 1, index + 6));
}

function isInternalApostrophe(text, index) {
  if (text[index] !== "’") return false;
  const previous = index ? text[index - 1] : "";
  const following = index + 1 < text.length ? text[index + 1] : "";
  return (isLatin(previous) && isLatin(following))
    || /^(?:\d{2}|\d{4})s\b/iu.test(text.slice(index + 1, index + 6));
}

function visibleProjection(text) {
  let visible = "";
  const explicit = new Map();
  for (let index = 0; index < text.length;) {
    const char = text[index];
    if (char === B_ON || char === B_OFF) {
      index += 1;
      continue;
    }
    if (char === FN) {
      const closing = text.indexOf(FN, index + 1);
      if (closing > index && /^\d+$/u.test(text.slice(index + 1, closing))) {
        index = closing + 1;
        continue;
      }
    }
    const marker = QUOTE_MARKERS.get(char);
    if (marker) {
      explicit.set(visible.length, marker.locale);
      visible += marker.text;
      index += 1;
      continue;
    }
    visible += char;
    index += 1;
  }
  return { visible, explicit };
}

function classifyQuoteLocales(text, explicit = new Map()) {
  const decisions = new Map(explicit);
  const stacks = new Map([["“", []], ["‘", []]]);
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (isInternalApostrophe(text, index)) {
      decisions.set(index, "en");
    } else if (CLOSE_TO_OPEN.has(char) && stacks.get(CLOSE_TO_OPEN.get(char)).length) {
      const opening = CLOSE_TO_OPEN.get(char);
      const start = stacks.get(opening).pop();
      const explicitLocales = new Set([explicit.get(start), explicit.get(index)].filter(Boolean));
      const locale = explicitLocales.size === 1
        ? [...explicitLocales][0]
        : (explicitLocales.size > 1 ? null : dominantLocale(text.slice(start + 1, index)) || dominantLocale(text));
      if (locale) {
        decisions.set(start, locale);
        decisions.set(index, locale);
      }
    } else if (isApostrophe(text, index)) {
      decisions.set(index, "en");
    } else if (OPEN_TO_CLOSE.has(char)) {
      stacks.get(char).push(index);
    }
  }
  return decisions;
}

function fontWithQuoteHint(font, locale) {
  return { ...font, hint: locale === "zh" ? "eastAsia" : "default" };
}

function quoteRun(char, locale, { size, bold, font }) {
  return new TextRun({ text: char, bold, size, font: fontWithQuoteHint(font, locale) });
}

function appendTextRuns(runs, text, visibleOffset, decisions, options) {
  let plain = "";
  const flush = () => {
    if (!plain) return;
    runs.push(new TextRun({ text: plain, bold: options.bold, size: options.size, font: options.font }));
    plain = "";
  };
  for (let index = 0; index < text.length; index += 1) {
    const locale = decisions.get(visibleOffset + index);
    if (locale && "“”‘’".includes(text[index])) {
      flush();
      runs.push(quoteRun(text[index], locale, options));
    } else {
      plain += text[index];
    }
  }
  flush();
}

function runsOf(text, { size = 24, baseBold = false, font = bodyFont } = {}) {
  const runs = [];
  const { visible, explicit } = visibleProjection(text);
  const decisions = classifyQuoteLocales(visible, explicit);
  let visibleOffset = 0;
  let bold = baseBold;
  for (let index = 0; index < text.length;) {
    const char = text[index];
    if (char === B_ON || char === B_OFF) {
      bold = char === B_ON ? true : baseBold;
      index += 1;
      continue;
    }
    if (char === FN) {
      const closing = text.indexOf(FN, index + 1);
      const number = closing > index ? text.slice(index + 1, closing) : "";
      if (/^\d+$/u.test(number)) {
        runs.push(new FootnoteReferenceRun(parseInt(number, 10)));
        index = closing + 1;
        continue;
      }
    }
    const marker = QUOTE_MARKERS.get(char);
    if (marker) {
      runs.push(quoteRun(marker.text, marker.locale, { size, bold, font }));
      visibleOffset += 1;
      index += 1;
      continue;
    }
    let end = index + 1;
    while (end < text.length && ![FN, B_ON, B_OFF].includes(text[end]) && !QUOTE_MARKERS.has(text[end])) end += 1;
    const part = text.slice(index, end);
    appendTextRuns(runs, part, visibleOffset, decisions, { size, bold, font });
    visibleOffset += part.length;
    index = end;
  }
  return runs;
}

function buildDocument(data) {
  const footnotes = {};
  for (const [num, text] of Object.entries(data.footnotes || {})) {
    footnotes[num] = {
      children: [new Paragraph({ spacing: { line: 240 }, children: runsOf(text, { size: 18 }) })],
    };
  }

  const children = [];
  children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 240, after: 120 },
    children: runsOf(data.title || "", { size: 32, baseBold: true, font: headFont }),
  }));
  if (data.subtitle) {
    children.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 160 },
      children: runsOf(data.subtitle, { size: 28, baseBold: true, font: headFont }),
    }));
  }
  if (data.author) {
    children.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 240 },
      children: runsOf(data.author, { size: 24, font: bodyFont }),
    }));
  }

  for (const block of data.blocks || []) {
    const plain = visibleProjection(block.text).visible;
    if (block.type === "h1" || block.type === "h1s") {
      children.push(new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 360, after: 240, line: 360 },
        children: runsOf(block.text, { size: 30, baseBold: true, font: headFont }),
      }));
    } else if (block.type === "h2") {
      children.push(new Paragraph({
        spacing: { before: 240, after: 120, line: 360 },
        children: runsOf(block.text, { size: 26, baseBold: true, font: headFont }),
      }));
    } else if (block.type === "li") {
      children.push(new Paragraph({
        numbering: { reference: "checklist", level: 0 },
        spacing: { line: 360 },
        children: runsOf(block.text),
      }));
    } else {
      const label = plain.startsWith("摘要：") || plain.startsWith("关键词：");
      children.push(new Paragraph({
        alignment: AlignmentType.JUSTIFIED,
        indent: label ? undefined : { firstLine: 480 },
        spacing: { line: 360 },
        children: runsOf(block.text),
      }));
    }
  }

  return new Document({
    styles: { default: { document: { run: { font: bodyFont, size: 24 } } } },
    numbering: {
      config: [{
        reference: "checklist",
        levels: [{
          level: 0,
          format: LevelFormat.DECIMAL,
          text: "%1.",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }],
      }],
    },
    footnotes,
    sections: [{
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1474, right: 1474, bottom: 1474, left: 1474 },
        },
      },
      children,
    }],
  });
}

function main() {
  const [,, jsonPath, outPath] = process.argv;
  if (!jsonPath || !outPath) {
    console.error("usage: node build_docx.js <content.json> <output.docx>");
    process.exit(1);
  }
  const data = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));
  Packer.toBuffer(buildDocument(data)).then((buffer) => {
    fs.writeFileSync(outPath, buffer);
    console.log("written:", outPath, buffer.length, "bytes");
  });
}

if (require.main === module) main();

module.exports = {
  bodyFont,
  headFont,
  buildDocument,
  classifyQuoteLocales,
  fontWithQuoteHint,
  runsOf,
  visibleProjection,
};
