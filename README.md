# SwiftTerm Public Site

This repository hosts the public SwiftTerm website for App Store Connect URLs.

Expected GitHub Pages URLs:

- Marketing URL: `https://ninjatomonline.github.io/swiftterm-site/`
- Support URL: `https://ninjatomonline.github.io/swiftterm-site/support.html`
- Privacy Policy URL: `https://ninjatomonline.github.io/swiftterm-site/privacy.html`

## Publish Flow

1. Export the site from the private SwiftTerm app repo:

   ```sh
   Scripts/export_hosted_site.sh
   ```

2. Copy or push the contents of `/tmp/swiftterm-site` into this public repo.
3. In GitHub, enable Pages with GitHub Actions as the source.
4. Confirm the Pages deployment succeeds and enter the URLs above in App Store Connect.

If a custom domain is added later, update `robots.txt`, `sitemap.xml`, this README, and the App Store Connect URLs in the private app repo handoff docs.
