# SwiftTerm Public Site

This repository hosts the public SwiftTerm website for App Store Connect URLs.
The source package is maintained in the private SwiftTerm app repo under
`Release/HostedPages/`; this public repo should only contain the exported static
site bundle.

Canonical public URLs:

- Marketing URL: `https://swiftterm.app/`
- FAQ URL: `https://swiftterm.app/faq.html`
- What's New URL: `https://swiftterm.app/whats-new.html`
- Press URL: `https://swiftterm.app/press.html`
- Support URL: `https://swiftterm.app/support.html`
- Privacy Policy URL: `https://swiftterm.app/privacy.html`

## Publish Flow

1. Export the site from the private SwiftTerm app repo:

   ```sh
   Scripts/export_hosted_site.sh
   ```

2. Copy or push the contents of `/tmp/swiftterm-site` into this public repo.
3. In GitHub Pages settings, set the custom domain to `swiftterm.app` and enable HTTPS after the certificate is issued.
4. Confirm the Pages deployment succeeds and enter the URLs above in App Store Connect.

The Pages workflow runs the hosted-site audit before deployment. You can run the same audit locally from the exported public repo with:

```sh
python3 .github/scripts/audit_hosted_site.py --hosted-root .
```

DNS should point the apex/root domain to GitHub Pages, with optional `www` configured as a CNAME to `ninjatomonline.github.io`.
