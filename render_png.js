#!/usr/bin/env node
"use strict";

const fs = require("fs/promises");
const path = require("path");

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

function writeError(code, message) {
  process.stdout.write(JSON.stringify({ code, message }));
}

function loadPlaywright() {
  try {
    return require("playwright");
  } catch (firstError) {
    try {
      return require("@playwright/test");
    } catch (_secondError) {
      const error = new Error("Playwright is required for PNG rendering. Install local dependencies with npm install, then install Chromium with npx playwright install chromium.");
      error.code = "render_dependency_unavailable";
      throw error;
    }
  }
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function normalizeSlide(slide, index, total) {
  const type = slide.type === "hook" || slide.type === "closing" || slide.type === "body" ? slide.type : "body";
  return {
    slideNumber: Number(slide.slideNumber || index + 1),
    type,
    text: String(slide.text || "").trim(),
    visualDirection: String(slide.visualDirection || "").trim(),
    isLast: index === total - 1,
  };
}

function fontRules(type) {
  if (type === "hook") {
    return { start: 76, min: 58 };
  }
  if (type === "closing") {
    return { start: 64, min: 48 };
  }
  return { start: 62, min: 46 };
}

function slideHtml(payload, slide, index, total) {
  const brand = payload.brand || {};
  const title = escapeHtml(payload.content && payload.content.title);
  const callToAction = escapeHtml(payload.content && payload.content.callToAction);
  const sourceCredit = escapeHtml(payload.content && payload.content.sourceCreditSuggestion);
  const footer = escapeHtml(brand.footer || "Review kembali sebelum upload agar tidak salah konteks.");
  const subtitle = escapeHtml(brand.subtitle || "");
  const primary = escapeHtml(brand.primary || "Annotasi Hikmah");
  const label = slide.type === "hook" ? "Renungan" : slide.type === "closing" ? "Catatan" : "Hikmah";
  const rules = fontRules(slide.type);
  const closingCta = slide.type === "closing" && callToAction ? `<div class="cta">${callToAction}</div>` : "";
  const source = slide.type === "closing" && sourceCredit ? `<div class="source">${sourceCredit}</div>` : "";
  const hookTitle = slide.type === "hook" && title ? `<div class="title">${title}</div>` : "";
  const visual = slide.visualDirection ? `<div class="visual-note">${escapeHtml(slide.visualDirection)}</div>` : "";

  return `<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=${payload.width}, height=${payload.height}, initial-scale=1">
  <style>
    * {
      box-sizing: border-box;
    }
    html,
    body {
      margin: 0;
      width: ${payload.width}px;
      height: ${payload.height}px;
      background: #12110d;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
      letter-spacing: 0;
    }
    .canvas {
      position: relative;
      width: ${payload.width}px;
      height: ${payload.height}px;
      overflow: hidden;
      color: #f7efd9;
      background:
        radial-gradient(circle at 15% 8%, rgba(196, 154, 83, 0.20), transparent 34%),
        linear-gradient(145deg, #191710 0%, #0e0d0a 58%, #201b12 100%);
      padding: 92px 96px 80px;
    }
    .canvas::before {
      content: "";
      position: absolute;
      inset: 42px;
      border: 2px solid rgba(211, 174, 103, 0.22);
      pointer-events: none;
    }
    .canvas::after {
      content: "";
      position: absolute;
      left: 96px;
      right: 96px;
      top: 195px;
      height: 1px;
      background: linear-gradient(90deg, rgba(222, 189, 119, 0.0), rgba(222, 189, 119, 0.46), rgba(222, 189, 119, 0.0));
    }
    .brand-row {
      position: relative;
      z-index: 1;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 28px;
      min-height: 76px;
    }
    .brand {
      color: #ead49f;
      font-size: 30px;
      font-weight: 700;
      line-height: 1.1;
    }
    .count {
      min-width: 94px;
      color: #caa65e;
      font-size: 28px;
      font-weight: 650;
      text-align: right;
    }
    .label {
      display: inline-flex;
      width: fit-content;
      margin-top: 76px;
      color: #e1bd70;
      font-size: 28px;
      font-weight: 650;
      text-transform: uppercase;
    }
    .content {
      position: relative;
      z-index: 1;
      display: flex;
      min-height: 720px;
      max-height: 760px;
      flex-direction: column;
      justify-content: center;
      padding: 30px 0;
    }
    .title {
      margin-bottom: 28px;
      color: #cfad69;
      font-size: 34px;
      font-weight: 650;
      line-height: 1.25;
    }
    .slide-text {
      max-height: 565px;
      color: #fff7df;
      font-size: ${rules.start}px;
      font-weight: ${slide.type === "hook" ? 760 : 680};
      line-height: 1.16;
      overflow-wrap: anywhere;
      white-space: pre-line;
    }
    .hook .slide-text {
      line-height: 1.08;
    }
    .visual-note {
      margin-top: 38px;
      max-height: 110px;
      color: #c7b98f;
      font-size: 28px;
      line-height: 1.32;
      overflow: hidden;
    }
    .cta {
      margin-top: 42px;
      color: #e9d6a6;
      font-size: 34px;
      font-weight: 650;
      line-height: 1.25;
    }
    .source {
      margin-top: 24px;
      color: #b9ad86;
      font-size: 25px;
      line-height: 1.3;
    }
    .subtitle {
      position: absolute;
      left: 96px;
      right: 96px;
      bottom: 122px;
      color: #bdb18a;
      font-size: 26px;
      line-height: 1.28;
    }
    .footer {
      position: absolute;
      left: 96px;
      right: 96px;
      bottom: 74px;
      color: #a79b78;
      font-size: 25px;
      line-height: 1.2;
    }
    .accent {
      position: absolute;
      right: 96px;
      bottom: 215px;
      width: 132px;
      height: 4px;
      background: #d8b46f;
    }
  </style>
</head>
<body>
  <main class="canvas ${slide.type}">
    <div class="brand-row">
      <div class="brand">${primary}</div>
      <div class="count">${String(index + 1).padStart(2, "0")}/${String(total).padStart(2, "0")}</div>
    </div>
    <div class="label">${escapeHtml(label)}</div>
    <section class="content">
      ${hookTitle}
      <div class="slide-text" data-start-font="${rules.start}" data-min-font="${rules.min}">${escapeHtml(slide.text)}</div>
      ${visual}
      ${closingCta}
      ${source}
    </section>
    ${slide.type === "hook" && subtitle ? `<div class="subtitle">${subtitle}</div>` : ""}
    <div class="accent"></div>
    <div class="footer">${footer}</div>
  </main>
</body>
</html>`;
}

async function ensureTextFits(page, slide) {
  const fit = await page.evaluate(() => {
    const text = document.querySelector(".slide-text");
    const content = document.querySelector(".content");
    if (!text || !content) {
      return { ok: false, fontSize: 0 };
    }
    const min = Number(text.getAttribute("data-min-font") || 46);
    let size = Number(text.getAttribute("data-start-font") || 60);
    while ((text.scrollHeight > text.clientHeight || content.scrollHeight > content.clientHeight) && size > min) {
      size -= 2;
      text.style.fontSize = `${size}px`;
    }
    return {
      ok: text.scrollHeight <= text.clientHeight && content.scrollHeight <= content.clientHeight,
      fontSize: size,
      textScrollHeight: text.scrollHeight,
      textClientHeight: text.clientHeight,
      contentScrollHeight: content.scrollHeight,
      contentClientHeight: content.clientHeight,
    };
  });
  if (!fit.ok) {
    const error = new Error(`Slide ${slide.slideNumber} text is too long to render without overflow.`);
    error.code = "slide_text_too_long";
    throw error;
  }
}

async function renderSlides(payload) {
  if (payload.templateName !== "annotasi_hikmah_dark") {
    const error = new Error("Template was not found.");
    error.code = "template_not_found";
    throw error;
  }

  const slides = payload.content && Array.isArray(payload.content.slides) ? payload.content.slides : [];
  if (slides.length < 1) {
    const error = new Error("Content package has no slides.");
    error.code = "no_slides";
    throw error;
  }

  await fs.mkdir(payload.outputDir, { recursive: true });

  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({ args: ["--no-sandbox"] });
  const files = [];
  try {
    const page = await browser.newPage({
      viewport: { width: Number(payload.width), height: Number(payload.height) },
      deviceScaleFactor: 1,
    });
    for (let index = 0; index < slides.length; index += 1) {
      const slide = normalizeSlide(slides[index], index, slides.length);
      if (!slide.text) {
        const error = new Error(`Slide ${index + 1} has no text.`);
        error.code = "invalid_slide";
        throw error;
      }
      const html = slideHtml(payload, slide, index, slides.length);
      await page.setContent(html, { waitUntil: "load" });
      await page.evaluate(() => {
        if (!document.fonts || !document.fonts.ready) {
          return true;
        }
        return document.fonts.ready.then(() => true);
      });
      await ensureTextFits(page, slide);
      const filename = `slide-${String(index + 1).padStart(2, "0")}.png`;
      const filePath = path.resolve(payload.outputDir, filename);
      await page.screenshot({ path: filePath, type: "png", fullPage: false });
      files.push({
        slideNumber: index + 1,
        filename,
        path: filePath,
        mimeType: "image/png",
      });
    }
  } finally {
    await browser.close();
  }
  return files;
}

async function main() {
  try {
    const raw = await readStdin();
    const payload = JSON.parse(raw);
    const files = await renderSlides(payload);
    process.stdout.write(JSON.stringify({ files }));
  } catch (error) {
    writeError(error.code || "png_generation_failed", error.message || "PNG generation failed.");
    process.exit(1);
  }
}

main();
