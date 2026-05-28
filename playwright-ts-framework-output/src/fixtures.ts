import { test as base, expect } from '@playwright/test';

import { HomePage } from './pages/HomePage';


type Fixtures = {

  homePage: HomePage;

};

export const test = base.extend<Fixtures>({

  homePage: async ({ page }, use) => {
    await use(new HomePage(page));
  },

});

export { expect };
