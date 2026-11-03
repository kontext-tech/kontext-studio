/** Screen: the profile tab on the account page. */
export default {
   id: "screen:account-profile",
   page: "11-account",
   stage: "configured",
   order: 110,
   slot: 1,
   goto: "/account",
   steps: [
      {
         id: "account-profile",
         caption:
            "**Account Settings** holds your profile: name, email, language, and the local account details. **Edit Profile** changes them in place.",
         before: async (page) => {
            await page.getByText("Raymond Tang").first().waitFor();
         },
         screenshotTarget: (page) => page.locator(".ant-card").first()
      },
      {
         id: "edit-profile",
         caption:
            "Select **Edit Profile** to change the first name, last name, and preferred language. The email address is fixed; **Save** updates the local profile and **Cancel** discards the change.",
         before: async (page) => {
            await page.getByRole("button", { name: "Edit Profile" }).click();
            await page.getByText("Edit Your Profile").waitFor();
         },
         screenshotTarget: (page) => page.locator(".ant-card").first()
      }
   ]
};
