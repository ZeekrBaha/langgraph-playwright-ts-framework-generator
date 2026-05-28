import { test, expect } from '../src/fixtures';


test.describe.configure({ tag: ['@smoke'] });


test.describe('HomeFlow', () => {
  test('should display the HomePage heading', async ({ page, HomePage }) => {

    await test.step('Go to HomePage', async () => {
      await HomePage.goto();
    });



    await expect(HomePage.heading).toBeVisible();

  });
});
