import { defineConfig } from '@playwright/test'
import principal from './playwright.config'

/** First installation: use only the isolated API with an empty database. */
export default defineConfig({
  ...principal,
  testIgnore: [],
  testMatch: ['**/registro-inicial.spec.ts'],
})
