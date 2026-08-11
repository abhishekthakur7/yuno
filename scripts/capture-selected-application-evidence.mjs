import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { chromium } from '@playwright/test'

const baseUrl = process.env.YUNO_CAPTURE_URL || 'http://127.0.0.1:5173'
const outputRoot = path.join(process.cwd(), 'screenshots', 'selected-application')
const viewports = [
  { width: 1440, height: 1000 },
  { width: 1366, height: 768 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
]
const routes = [
  ['home', '/'],
  ['onboarding', '/app/onboarding'],
  ['learn-roadmap', '/app/learn-roadmap'],
  ['topic-studio', '/app/topic-studio'],
  ['interview-hub', '/app/interview-hub'],
  ['practice', '/app/practice'],
  ['mock', '/app/mock'],
  ['reports', '/app/reports'],
  ['evidence', '/app/evidence'],
  ['imports', '/app/imports'],
  ['canonical-updates', '/app/canonical-updates'],
  ['search', '/app/search'],
  ['jobs', '/app/jobs'],
  ['settings', '/app/settings'],
]
const practiceAnswer = 'The commit-before-ack window needs an atomic idempotency key with an explicit retention policy.'
const fixtureDraft = 'Fail closed for reservation creation, return a retryable failure, and keep the message unacknowledged. Failing open can create an irreversible duplicate. Bound retries, expose the dependency failure, and recover from the queue rather than claiming availability.'

function isLocal(url) {
  if (url.startsWith('data:') || url.startsWith('blob:')) return true
  const parsed = new URL(url)
  return ['localhost', '127.0.0.1', '::1', '[::1]'].includes(parsed.hostname.toLowerCase())
}

const browser = await chromium.launch()
const failures = []
let count = 0

try {
  await mkdir(outputRoot, { recursive: true })
  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport, reducedMotion: 'reduce' })
    const page = await context.newPage()
    const size = `${viewport.width}x${viewport.height}`

    page.on('console', (message) => {
      if (message.type() === 'error') failures.push(`${size} console: ${message.text()}`)
    })
    page.on('pageerror', (error) => failures.push(`${size} page: ${error.message}`))
    page.on('request', (request) => {
      if (!isLocal(request.url())) failures.push(`${size} external request: ${request.method()} ${request.url()}`)
    })
    await page.addInitScript(() => {
      if (sessionStorage.getItem('yuno.capture.initialized')) return
      for (const key of Object.keys(localStorage)) if (key.startsWith('yuno.')) localStorage.removeItem(key)
      sessionStorage.setItem('yuno.capture.initialized', 'true')
    })

    const capture = async (name) => {
      await page.screenshot({ path: path.join(outputRoot, `${name}--${size}.png`), fullPage: false })
      count += 1
    }
    const open = async (route) => {
      await page.goto(`${baseUrl}${route}`)
      await page.locator('[data-app="yuno-learning"]').waitFor()
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
      if (overflow) failures.push(`${size} ${route}: horizontal overflow`)
    }

    for (const [name, route] of routes) {
      await open(route)
      await capture(name)
    }

    await open('/app/onboarding')
    await page.getByRole('button', { name: /Preview full roadmap/i }).click()
    await capture('onboarding-roadmap-preview')

    await open('/app/topic-studio')
    if (viewport.width <= 1000) {
      await page.getByRole('button', { name: /Course content/i }).click()
      await capture('topic-course-content-drawer')
      await page.getByRole('button', { name: /Close course content/i }).click()
    }
    await page.getByRole('button', { name: /Submit evidence/i }).click()
    await open('/app/evidence')
    await page.getByRole('heading', { name: /Static fixture checks/i }).waitFor()
    await capture('evidence-submitted')

    await open('/app/practice')
    await page.getByRole('textbox', { name: /Your response/i }).fill(practiceAnswer)
    await page.getByRole('button', { name: /Submit response/i }).click()
    await capture('practice-feedback')

    await open('/app/mock')
    await page.getByRole('button', { name: /Save & exit/i }).click()
    await capture('mock-safe-exit-dialog')
    await page.getByRole('button', { name: /Keep answering/i }).click()
    await page.getByRole('textbox', { name: /Your response/i }).fill(fixtureDraft)
    await page.getByRole('button', { name: /Complete interview/i }).click()
    await capture('mock-completion-dialog')
    await page.getByRole('button', { name: /Complete & view report/i }).click()
    await page.getByText('Exact-fixture evaluation', { exact: true }).waitFor()
    await capture('reports-completed')

    await context.close()
  }
} finally {
  await browser.close()
}

if (failures.length) {
  console.error(failures.join('\n'))
  process.exitCode = 1
} else {
  console.log(`Captured ${count} selected-application screenshots with no runtime, network, or overflow failures.`)
}
