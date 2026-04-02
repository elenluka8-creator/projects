import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["en", "ru", "sr", "es"],
  defaultLocale: "en",
});
