#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 4) {
  stop("usage: render_exhibit.R SPEC DATA STYLE OUTDIR")
}

`%||%` <- function(x, y) if (is.null(x)) y else x

required_packages <- c("jsonlite", "ggplot2", "svglite", "ragg", "systemfonts")
missing_packages <- required_packages[!vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing_packages) > 0) {
  stop(paste("missing R packages:", paste(missing_packages, collapse = ", ")))
}

spec_path <- normalizePath(args[[1]], mustWork = TRUE)
data_path <- normalizePath(args[[2]], mustWork = TRUE)
style_path <- normalizePath(args[[3]], mustWork = TRUE)
outdir <- args[[4]]
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)

spec <- jsonlite::fromJSON(spec_path, simplifyVector = FALSE)
style <- jsonlite::fromJSON(style_path, simplifyVector = TRUE)
kind <- spec$kind
if (grepl("\\.json$", data_path, ignore.case = TRUE)) {
  data_payload <- jsonlite::fromJSON(data_path, simplifyDataFrame = TRUE)
  data <- data_payload$rows
} else {
  data <- utils::read.csv(data_path, stringsAsFactors = FALSE, check.names = FALSE, colClasses = "character")
}
if (!is.data.frame(data) || nrow(data) == 0) {
  stop("companion data has no rows")
}
if (any(!nzchar(names(data))) || anyDuplicated(names(data))) {
  stop("companion data requires non-empty unique column names")
}

numeric_fields <- c("estimate", "std_error", "conf_low", "conf_high", "confidence_level", "sample_n")
for (field in numeric_fields) {
  if (field %in% names(data)) {
    suppressWarnings(data[[field]] <- as.numeric(data[[field]]))
  } else {
    data[[field]] <- NA_real_
  }
}
if (any(!is.finite(data$estimate))) stop("estimate must be finite")
if (any(!is.finite(data$sample_n) | data$sample_n < 1 | data$sample_n != floor(data$sample_n))) {
  stop("sample_n must be a positive integer")
}
if (any(!is.finite(data$confidence_level) | data$confidence_level <= 0 | data$confidence_level >= 1)) {
  stop("confidence_level must be finite and between zero and one")
}
if (any(!is.na(data$std_error) & (!is.finite(data$std_error) | data$std_error < 0))) {
  stop("std_error must be missing or a non-negative finite number")
}
ci_mismatch <- xor(is.na(data$conf_low), is.na(data$conf_high))
ci_invalid <- !is.na(data$conf_low) & (
  !is.finite(data$conf_low) | !is.finite(data$conf_high) |
    data$conf_low > data$conf_high | data$estimate < data$conf_low | data$estimate > data$conf_high
)
if (any(ci_mismatch | ci_invalid)) stop("confidence intervals must be finite pairs containing the estimate")
for (field in c("model_label", "group_label", "panel_label", "term", "color", "line_type", "marker")) {
  if (!field %in% names(data)) data[[field]] <- ""
  data[[field]][is.na(data[[field]])] <- ""
}
if (!"x" %in% names(data)) data$x <- NA
if (kind %in% c("event_study", "trend_or_binscatter")) {
  suppressWarnings(data$x <- as.numeric(data$x))
  if (any(!is.finite(data$x))) stop(paste(kind, "requires finite numeric x values"))
} else if (kind %in% c("marginal_effects", "predicted_probability")) {
  raw_x <- as.character(data$x)
  if (identical(spec$x_scale, "continuous")) {
    suppressWarnings(data$x <- as.numeric(raw_x))
    if (any(!is.finite(data$x))) stop("continuous x_scale requires finite numeric x values")
  } else if (identical(spec$x_scale, "ordered_category")) {
    if (any(is.na(raw_x) | !nzchar(raw_x))) stop("ordered_category x_scale requires non-empty x labels")
    data$x <- factor(raw_x, levels = unique(raw_x), ordered = TRUE)
  } else {
    stop("marginal-effects and predicted-probability exhibits require an explicit x_scale")
  }
}
series_separator <- style$labels$series_separator %||% " / "
series_key <- paste(data$model_label, data$group_label, sep = "\u001f")
series_display <- vapply(seq_len(nrow(data)), function(i) {
  parts <- c(data$model_label[[i]], data$group_label[[i]])
  parts <- parts[nzchar(parts)]
  if (length(parts) == 0) "series" else paste(parts, collapse = series_separator)
}, character(1))
key_levels <- unique(series_key)
display_levels <- series_display[match(key_levels, series_key)]
if (anyDuplicated(display_levels) > 0) {
  display_levels <- vapply(key_levels, function(key) {
    paste(strsplit(key, "\u001f", fixed = TRUE)[[1]], collapse = series_separator)
  }, character(1))
}
data$series <- display_levels[match(series_key, key_levels)]
x_is_discrete <- is.factor(data$x)

panel_presence <- nzchar(data$panel_label)
if (any(panel_presence) && !all(panel_presence)) {
  stop("panel_label must be empty for every row or non-empty for every row")
}

available_families <- unique(systemfonts::system_fonts()$family)
resolve_family <- function(slot) {
  primary <- style$fonts[[slot]]
  fallbacks <- unname(unlist(style$font_fallbacks[[slot]] %||% list()))
  candidates <- c(primary, fallbacks)
  candidates <- candidates[!is.na(candidates) & nzchar(candidates)]
  hits <- candidates[tolower(candidates) %in% tolower(available_families)]
  if (length(hits) == 0) {
    stop(paste("requested fonts are unavailable:", paste(candidates, collapse = ", ")))
  }
  hits[[1]]
}
font_slots <- names(style$fonts)
resolved_fonts <- stats::setNames(lapply(font_slots, resolve_family), font_slots)
base_family <- resolved_fonts$base
font_fallback_used <- any(vapply(font_slots, function(slot) {
  !identical(tolower(resolved_fonts[[slot]]), tolower(style$fonts[[slot]]))
}, logical(1)))
y_label <- spec$y_label %||% paste(spec$quantity, paste0("(", spec$unit, ")"))
x_label_relative <- spec$x_label %||% (style$labels$relative_period %||% "Relative period")
x_label_free <- spec$x_label
legend_position <- if (length(unique(data$series)) > 1) "bottom" else "none"
base_size <- as.numeric(style$min_font_pt)
palette <- unname(unlist(style$palette))
allowed_lines <- unname(unlist(style$line_types))
allowed_markers <- as.character(unname(unlist(style$markers)))
if (any(!data$line_type %in% allowed_lines)) stop("line_type is not allowed by the selected style profile")
if (any(!data$marker %in% allowed_markers)) stop("marker is not allowed by the selected style profile")
declared_colours <- data$color[nzchar(data$color)]
if (any(!tolower(declared_colours) %in% tolower(palette))) stop("color is not allowed by the selected style profile")
series_levels <- unique(data$series)
for (series_id in series_levels) {
  series_rows <- data[data$series == series_id, , drop = FALSE]
  if (
    length(unique(series_rows$color)) != 1 ||
      length(unique(series_rows$line_type)) != 1 ||
      length(unique(series_rows$marker)) != 1
  ) {
    stop("a model/group series changes color, line, or marker identity across rows or panels")
  }
}
visual_rows <- data[match(series_levels, data$series), , drop = FALSE]
colour_values <- visual_rows$color
missing_colour <- is.na(colour_values) | colour_values == ""
if (sum(missing_colour) > length(palette)) stop("style palette has too few colours")
colour_values[missing_colour] <- palette[seq_len(sum(missing_colour))]
colour_values <- stats::setNames(colour_values, series_levels)
line_values <- stats::setNames(visual_rows$line_type, series_levels)
shape_values <- suppressWarnings(as.numeric(visual_rows$marker))
if (any(!is.finite(shape_values))) stop("marker must be an R numeric shape code")
shape_values <- stats::setNames(shape_values, series_levels)

theme_avereth <- ggplot2::theme_minimal(base_size = base_size, base_family = base_family) +
  ggplot2::theme(
    plot.title = ggplot2::element_blank(),
    panel.grid.minor = ggplot2::element_blank(),
    legend.position = legend_position,
    legend.title = ggplot2::element_blank(),
    axis.title = ggplot2::element_text(size = base_size),
    axis.text = ggplot2::element_text(size = base_size)
  )

if (kind == "coefficient_forest") {
  data$term <- factor(data$term, levels = rev(unique(data$term)))
  plot <- ggplot2::ggplot(data, ggplot2::aes(x = term, y = estimate, colour = series, shape = series)) +
    ggplot2::geom_hline(yintercept = as.numeric(spec$reference_value %||% 0), linewidth = 0.35, colour = "grey45") +
    ggplot2::geom_errorbar(ggplot2::aes(ymin = conf_low, ymax = conf_high), width = 0.15, position = ggplot2::position_dodge(width = 0.45)) +
    ggplot2::geom_point(position = ggplot2::position_dodge(width = 0.45), size = 2) +
    ggplot2::coord_flip() + ggplot2::labs(x = x_label_free, y = y_label)
} else if (kind == "event_study") {
  plot <- ggplot2::ggplot(data, ggplot2::aes(x = x, y = estimate, colour = series, shape = series, linetype = series)) +
    ggplot2::geom_hline(yintercept = as.numeric(spec$reference_value), linewidth = 0.35, colour = "grey45") +
    ggplot2::geom_vline(xintercept = as.numeric(spec$treatment_boundary), linewidth = 0.35, linetype = "dashed", colour = "grey45") +
    ggplot2::geom_errorbar(ggplot2::aes(ymin = conf_low, ymax = conf_high), width = 0.12) +
    ggplot2::geom_line(linewidth = 0.45) + ggplot2::geom_point(size = 2) +
    ggplot2::scale_x_continuous(breaks = sort(unique(data$x))) +
    ggplot2::labs(x = x_label_relative, y = y_label)
} else if (kind %in% c("marginal_effects", "predicted_probability", "trend_or_binscatter")) {
  plot <- ggplot2::ggplot(data, ggplot2::aes(x = x, y = estimate, colour = series, shape = series, linetype = series, group = series))
  if (all(c("conf_low", "conf_high") %in% names(data)) && any(is.finite(data$conf_low)) && any(is.finite(data$conf_high))) {
    if (x_is_discrete) {
      plot <- plot + ggplot2::geom_errorbar(ggplot2::aes(ymin = conf_low, ymax = conf_high), width = 0.12)
    } else {
      plot <- plot + ggplot2::geom_ribbon(ggplot2::aes(ymin = conf_low, ymax = conf_high, fill = series), alpha = 0.12, colour = NA)
    }
  }
  plot <- plot + ggplot2::geom_line(linewidth = 0.55) + ggplot2::geom_point(size = 1.8) +
    ggplot2::labs(x = x_label_free, y = y_label)
} else if (kind == "regression_or_balance_table") {
  data$row <- rev(seq_len(nrow(data)))
  data$estimate_text <- ifelse(
    is.finite(data$conf_low) & is.finite(data$conf_high),
    sprintf("%.3f [%.3f, %.3f]", data$estimate, data$conf_low, data$conf_high),
    sprintf("%.3f", data$estimate)
  )
  plot <- ggplot2::ggplot(data) +
    ggplot2::geom_text(ggplot2::aes(x = 0, y = row, label = term), hjust = 0, family = base_family, size = base_size / 2.845276) +
    ggplot2::geom_text(ggplot2::aes(x = 1, y = row, label = model_label), hjust = 0.5, family = base_family, size = base_size / 2.845276) +
    ggplot2::geom_text(ggplot2::aes(x = 2, y = row, label = estimate_text), hjust = 1, family = base_family, size = base_size / 2.845276) +
    ggplot2::geom_hline(yintercept = c(0.5, nrow(data) + 0.5), linewidth = 0.45) +
    ggplot2::coord_cartesian(xlim = c(0, 2), clip = "off") + ggplot2::theme_void(base_family = base_family, base_size = base_size)
} else {
  stop(paste("unsupported exhibit kind:", kind))
}

if (kind != "regression_or_balance_table") {
  plot <- plot + theme_avereth +
    ggplot2::scale_colour_manual(values = colour_values) +
    ggplot2::scale_fill_manual(values = colour_values) +
    ggplot2::scale_linetype_manual(values = line_values) +
    ggplot2::scale_shape_manual(values = shape_values)
  panel_values <- unique(data$panel_label[nzchar(data$panel_label)])
  if (length(panel_values) > 1) {
    plot <- plot + ggplot2::facet_wrap(ggplot2::vars(panel_label))
  }
}

width <- as.numeric(style$width_inches)
height <- as.numeric(style$height_inches)
dpi <- as.numeric(style$dpi)
formats <- unname(unlist(spec$formats))
if ("pdf" %in% formats) {
  if (!capabilities("cairo")) stop("Cairo PDF support is unavailable")
  ggplot2::ggsave(file.path(outdir, "exhibit.pdf"), plot, device = grDevices::cairo_pdf, width = width, height = height, units = "in")
}
if ("svg" %in% formats) {
  ggplot2::ggsave(file.path(outdir, "exhibit.svg"), plot, device = svglite::svglite, width = width, height = height, units = "in")
}
if ("png" %in% formats) {
  ggplot2::ggsave(file.path(outdir, "exhibit.png"), plot, device = ragg::agg_png, width = width, height = height, units = "in", dpi = dpi)
}

log_payload <- list(
  schema_version = "avereth-exhibit-render-log/v1",
  exhibit_id = spec$exhibit_id,
  renderer = "r/generic-ggplot2-v1",
  R = R.version.string,
  packages = as.list(vapply(required_packages, function(pkg) as.character(utils::packageVersion(pkg)), character(1))),
  requested_fonts = style$fonts,
  resolved_fonts = resolved_fonts,
  render_checks = list(
    font_min_pt = base_size,
    requested_fonts_available = TRUE,
    font_fallback_used = font_fallback_used,
    glyph_fallback_checked = FALSE,
    dpi = dpi
  )
)
jsonlite::write_json(log_payload, file.path(outdir, "render_log.json"), pretty = TRUE, auto_unbox = TRUE)
