import { createHash } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import pngjs from 'pngjs';
import { chromium } from 'playwright-core';

const { PNG } = pngjs;

export function boardDigest(image, { view, board }) {
  const png = PNG.sync.read(image);
  if (png.width !== view.width || png.height !== view.height) {
    throw new Error('Screenshot crop dimensions changed');
  }
  const x = board.x - view.x;
  const y = board.y - view.y;
  const digest = createHash('sha256');
  for (let row = 0; row < board.height; row++) {
    const start = ((y + row) * png.width + x) * 4;
    digest.update(png.data.subarray(start, start + board.width * 4));
  }
  return digest.digest('hex');
}

export async function bindView(settings, connect = endpoint =>
  chromium.connectOverCDP(endpoint, { timeout: 5000, noDefaults: true })) {
  const browser = await connect(settings.endpoint);
  try {
    const tabs = browser.contexts().flatMap(context => context.pages())
      .filter(page => page.url() === settings.url);
    if (tabs.length !== 1) throw new Error('Expected exactly one tab at the configured match URL');
    const [tab] = tabs;
    let navigated = false;
    tab.on('framenavigated', frame => {
      if (frame === tab.mainFrame()) navigated = true;
    });
    const assertBound = () => {
      if (navigated || tab.isClosed() || tab.url() !== settings.url) {
        throw new Error('The bound match tab navigated or closed');
      }
    };
    async function capture() {
      assertBound();
      const image = await tab.screenshot({ clip: settings.view, scale: 'css', timeout: 5000 });
      assertBound();
      return { image, boardDigest: boardDigest(image, settings) };
    }

    return {
      async observe() {
        let previous = await capture();
        for (let attempt = 0; attempt < 5; attempt++) {
          await delay(250);
          const frame = await capture();
          if (frame.boardDigest === previous.boardDigest) return frame;
          previous = frame;
        }
        throw new Error('Board pixels did not settle');
      },
      async click([x, y]) {
        assertBound();
        await tab.mouse.click(x, y);
        assertBound();
      },
      close: () => browser.close(),
    };
  } catch (error) {
    await browser.close();
    throw error;
  }
}
