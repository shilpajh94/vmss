import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, test } from 'node:test'

// The token contracts in the design-theme / theme-mode specs, checked against
// theme.css itself (fix-dark-theme-rendering design.md D6).
const css = readFileSync(new URL('../../src/styles/theme.css', import.meta.url), 'utf8')

function tokens(block: string): Record<string, string> {
  return Object.fromEntries([...block.matchAll(/--color-([\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map(([, name, hex]) => [name, hex]))
}

const light = tokens(css.match(/@theme\s*{([\s\S]*?)\n}/)![1])
const dark = { ...light, ...tokens(css.match(/:root\[data-theme="dark"\]\s*{([\s\S]*?)\n}/)![1]) }

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (high + 0.05) / (low + 0.05)
}

for (const [name, theme] of [['light', light], ['dark', dark]] as const) {
  describe(`${name} theme tokens`, () => {
    test('primary buttons and step/badge numerals meet AA', () => {
      assert.ok(contrast(theme['on-primary'], theme.primary) >= 4.5)
      assert.ok(contrast(theme['text-secondary'], theme.border) >= 4.5)
    })

    test('text on a card inset meets AA', () => {
      assert.ok(contrast(theme.text, theme['surface-inset']) >= 4.5)
    })
  })
}

test('a card inset matches the card in light and lifts above it in dark', () => {
  assert.equal(light['surface-inset'], light.surface)
  assert.ok(luminance(dark['surface-inset']) > luminance(dark.surface))
})
