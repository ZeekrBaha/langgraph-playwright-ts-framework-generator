import { Page, Locator } from '@playwright/test';

export class HomePage {
  constructor(private readonly page: Page) {}




  readonly heading: Locator = this.page.getByRole('heading', { name: 'Welcome' });




  async goto(): Promise<void> {
    await this.page.goto('/');
  }


}
