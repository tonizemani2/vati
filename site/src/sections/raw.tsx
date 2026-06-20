import { readFileSync } from "fs";
import { join } from "path";

const HERO_CHAT_MARKUP = `
<div class="vati-hero-chat-shell">
  <form class="vati-hero-chat" action="https://chat.vaticinus.com" method="get">
    <label class="u-sr-only" for="vati-hero-chat-input">Ask Vaticinus a forecasting question</label>
    <div class="vati-hero-chat-row">
      <input id="vati-hero-chat-input" class="vati-hero-chat-input" name="q" type="text" autocomplete="off" required placeholder="Ask where value goes next..." />
      <input type="hidden" name="auto" value="1" />
      <input type="hidden" name="tier" value="council" />
      <input type="hidden" name="source" value="site" />
      <button class="vati-hero-chat-submit" type="submit">Ask</button>
    </div>
  </form>
  <div class="vati-hero-chat-prompts" aria-label="Example forecasting questions">
    <a href="https://chat.vaticinus.com?q=Where%20does%20the%20binding%20constraint%20in%20AI%20move%20next%3F&amp;auto=1&amp;tier=council&amp;source=site">AI bottleneck</a>
    <a href="https://chat.vaticinus.com?q=Is%20HVDC%20cable%20manufacturing%20the%20pace-setter%20for%20offshore%20grid%20buildout%3F&amp;auto=1&amp;tier=council&amp;source=site">Grid buildout</a>
    <a href="https://chat.vaticinus.com?q=Show%20me%20the%20leak-free%20scored%20record&amp;auto=1&amp;tier=council&amp;source=site">Scored record</a>
  </div>
</div>`;

const AI_ANSWER_BLOCK = `
<div class="vati-answer-block c-paragraph w-richtext u-mb-text u-rich-text u-text-style-large u-color-faded u-max-width-55ch">
  <h3>What is Vaticinus?</h3>
  <p>Vaticinus is an independent forecasting lab. We figure out where scarcity and value are headed, write the call down before anyone knows the answer, and let it get scored in public.</p>
  <p>Every call rests on one bet: rent goes to whatever input can't scale when demand arrives. So we look for the bottleneck a layer under the headline, check whether the market has already priced it, and put a date and a number on what would prove us wrong.</p>
</div>`;

type ImageSeoFix = {
  src: string;
  width: string;
  height: string;
  alt?: string;
  loading?: string;
};

const IMAGE_SEO_FIXES: ImageSeoFix[] = [
  { src: "/brand-mark.svg", width: "30", height: "30", alt: "Vaticinus brand mark" },
  { src: "/forecasts/previews/inelastic-needles-memo.png", width: "720", height: "932" },
  { src: "/forecasts/previews/long-horizon-memo.png", width: "720", height: "932" },
  { src: "/forecasts/previews/chips-memo.png", width: "720", height: "932" },
  { src: "/forecasts/previews/biotech-memo.png", width: "720", height: "932" },
  { src: "/forecasts/previews/space-memo.png", width: "720", height: "932" },
  {
    src: "/images/690cb136eef6de79e8f7d34d_vid_cover.avif",
    width: "3432",
    height: "1926",
    alt: "Vaticinus forecasting engine overview poster",
    loading: "lazy",
  },
  {
    src: "/images/69c0bb6c8521c9290a153aed_5f75a24490c8706c680a501e4ef1bf57_ico-play-white.svg",
    width: "24",
    height: "24",
    alt: "Play video",
    loading: "lazy",
  },
  {
    src: "/images/6911ef43d92c50f0fe493b41_tmp.png",
    width: "1296",
    height: "585",
    alt: "Vaticinus public forecasting benchmark chart",
    loading: "lazy",
  },
  {
    src: "/images/6911eeeb668f9d44687e0245_aib.png",
    width: "1296",
    height: "375",
    alt: "ForecastBench dataset-half benchmark chart",
    loading: "lazy",
  },
  {
    src: "/images/699d43110e92755210e6e449_ico-globus.svg",
    width: "20",
    height: "20",
    alt: "All topics",
    loading: "lazy",
  },
  {
    src: "/images/699d58498e3a66b1c915e281_ico-space.svg",
    width: "20",
    height: "20",
    alt: "Technology topic",
    loading: "lazy",
  },
  {
    src: "/images/699d586acc2bdad65b370a56_ico-bank.svg",
    width: "20",
    height: "20",
    alt: "Business topic",
    loading: "lazy",
  },
  {
    src: "/images/69c291023714cc0d26bb4193_currency-pounds.svg",
    width: "20",
    height: "20",
    alt: "Economics topic",
    loading: "lazy",
  },
  {
    src: "/images/69c29238917b85385886d545_ico-urgent.svg",
    width: "20",
    height: "20",
    alt: "Conflict topic",
    loading: "lazy",
  },
  {
    src: "/images/699d62a1ef8bde4a4b97ee2f_ico-arrow-right.svg",
    width: "20",
    height: "20",
    alt: "Open link",
    loading: "lazy",
  },
];

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function setAttribute(tag: string, attr: string, value: string): string {
  const attrPattern = new RegExp(`\\s${attr}="[^"]*"`);
  if (attrPattern.test(tag)) {
    return tag.replace(attrPattern, ` ${attr}="${value}"`);
  }
  return tag.replace(/>$/, ` ${attr}="${value}">`);
}

function applyImageSeoFixes(html: string): string {
  return IMAGE_SEO_FIXES.reduce((current, fix) => {
    const tagPattern = new RegExp(
      `<img\\b(?=[^>]*\\bsrc="${escapeRegExp(fix.src)}")[^>]*>`,
      "g",
    );
    return current.replace(tagPattern, (tag) => {
      let patched = setAttribute(tag, "width", fix.width);
      patched = setAttribute(patched, "height", fix.height);
      if (fix.alt !== undefined) patched = setAttribute(patched, "alt", fix.alt);
      if (fix.loading) patched = setAttribute(patched, "loading", fix.loading);
      return patched;
    });
  }, html);
}

function repairResearchFragment(html: string): string {
  return html
    .replace(
      '</a></div></div></div></div></div><div data-wf--spacer--section-space="small"',
      '</a></div></div></div></div><div data-wf--spacer--section-space="small"',
    )
    .replace(
      '<li>Politics</li><li>Economics</li><li>Crypto</li><li>Climate</li></ul></div></div></div></div></div><div data-wf--spacer--section-space="small"',
      '<li>Politics</li><li>Economics</li><li>Crypto</li><li>Climate</li></ul></div></div></div></div></div></div><div data-wf--spacer--section-space="small"',
    );
}

function enhanceFragment(name: string, html: string): string {
  let enhanced = applyImageSeoFixes(
    name === "research" ? repairResearchFragment(html) : html,
  );

  if (name === "hero") {
    enhanced = enhanced.replace(
      '<div id="heroh1" class="c-heading h1 w-richtext u-mb-7"><p>Forecasting where<br>scarcity moves next</p></div>',
      '<h1 id="heroh1" class="c-heading h1 w-richtext u-mb-7">Forecasting where<br>scarcity moves next</h1>',
    );
    enhanced = enhanced.replace(
      '<div id="heroP" class="c-paragraph w-richtext u-mb-text u-rich-text u-text-style-large u-color-faded u-max-width-50ch u-child-contain"><p>We read millions of research papers, trade flows, and supply records to find the input that quietly stops being elastic.</p><p>A deep-research engine paired with a forecasting model trained on our own leak-free data. Every call is dated, carries a kill-criterion, and is scored in public.</p></div>',
      '<div id="heroP" class="c-paragraph w-richtext u-mb-text u-rich-text u-text-style-large u-color-faded u-max-width-50ch u-child-contain"><p>We scan research, trade, and supply records for the input that stops scaling. Every dated call is falsifiable and scored.</p></div>',
    );
    if (!enhanced.includes("vati-hero-chat-input")) {
      enhanced = enhanced.replace(
        '</div><div id="herobtn"',
        `</div>${HERO_CHAT_MARKUP}<div id="herobtn"`,
      );
    }
    enhanced = enhanced.replace(
      /<div data-wf--button-main--style="primary" class="button_main_wrap"><div class="clickable_wrap u-cover-absolute"><a target="_blank" rel="noopener" href="https:\/\/chat\.vaticinus\.com" class="clickable_link w-inline-block"><span class="clickable_text u-sr-only">Try the chat<\/span><\/a><button type="button" class="clickable_btn"><span class="clickable_text u-sr-only">Try the chat<\/span><\/button><\/div><div aria-hidden="true" class="button_main_text u-text-style-main">Try the chat<\/div><\/div>/,
      "",
    );
  }

  if (name === "research" && !enhanced.includes("What is Vaticinus?")) {
    enhanced = enhanced.replace(
      '<div data-wf--spacer--section-space="small" class="u-section-spacer w-variant-d422cbd0-f212-c815-68df-63414354c21d u-pointer-off u-ignore-trim"></div><div class="research_contain-lg u-container">',
      `<div data-wf--spacer--section-space="small" class="u-section-spacer w-variant-d422cbd0-f212-c815-68df-63414354c21d u-pointer-off u-ignore-trim"></div><div class="research_contain-sm u-container-small">${AI_ANSWER_BLOCK}</div><div data-wf--spacer--section-space="small" class="u-section-spacer w-variant-d422cbd0-f212-c815-68df-63414354c21d u-pointer-off u-ignore-trim"></div><div class="research_contain-lg u-container">`,
    );
  }

  return enhanced;
}

// Server-only: reads the exact (localized, script-stripped) Webflow fragment at build
// time and injects it under the vendored stylesheet. The display:contents wrapper
// keeps the original <section> as the layout-participating element.
export function loadFragment(name: string): string {
  const html = readFileSync(
    join(process.cwd(), "src/sections/fragments", `${name}.html`),
    "utf8",
  );
  return enhanceFragment(name, html);
}

export function RawSection({ name }: { name: string }) {
  return (
    <div
      style={{ display: "contents" }}
      dangerouslySetInnerHTML={{ __html: loadFragment(name) }}
    />
  );
}
