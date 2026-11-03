const contentClip = async (page) => {
   // The card ends well above the fold, so a viewport shot is mostly
   // whitespace. The header carries Refresh and Prepare Environment, so crop to
   // the header plus the content rather than to the card alone.
   const container = await page.locator(".ant-layout-content").boundingBox();
   const heading = await page
      .getByRole("heading", { name: "Python Environment" })
      .boundingBox();
   const tabs = await page.locator(".ant-tabs").first().boundingBox();
   if (!container || !heading || !tabs) {
      throw new Error("Python environment layout is not measurable.");
   }
   const top = heading.y - 12;
   const bottom = Math.min(
      tabs.y + tabs.height + 24,
      container.y + container.height
   );
   return {
      x: container.x + 1,
      y: top,
      width: container.width - 2,
      height: bottom - top
   };
};

/** Screen: the Python runtime inspector. */
export default {
   id: "screen:python-environment",
   page: "12-python-environment",
   stage: "configured",
   order: 120,
   slot: 1,
   goto: "/python-environment",
   steps: [
      {
         id: "python-environment",
         caption:
            "**Python Environment** reports the runtime identity, backend, Python version, profile, and preparation status, with actions to prepare or refresh the runtime.",
         before: async (page) => {
            await page.getByText("Runtime Details").first().waitFor();
         },
         screenshotClip: contentClip
      },
      {
         id: "managed-packages",
         caption:
            "**Managed Packages** lists the packages that come with the selected runtime profile and the version and spec Kontext resolved for each one.",
         before: async (page) => {
            await page.getByRole("tab", { name: "Managed Packages" }).click();
            await page.locator(".ant-table").first().waitFor();
            await page.waitForTimeout(400);
         },
         screenshotClip: contentClip
      }
   ]
};
