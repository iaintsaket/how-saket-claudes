# Known false-positive patterns

These have been investigated and disproven in past hunts. Don't re-investigate them unless you have specific new evidence:

| Claim | Why it's a FP |
|---|---|
| "AES-GCM call is missing the authentication tag — only IV+ciphertext stored" | WebCrypto `subtle.encrypt({name:'AES-GCM'}, ...)` returns `ciphertext ‖ tag` as a single ArrayBuffer. `subtle.decrypt` validates the tag automatically. Code that splits only IV from "ciphertext" is correct. |
| "Glob library doesn't anchor — `example.com` matches `attacker-example.com.evil.com`" | picomatch, micromatch, minimatch all anchor by default via `^...$` in `compileRe`/`makeRe`. Read the compiled source to confirm before reporting. Only valid if `contains:true` or equivalent unanchored option is passed. |
| "Server Action accepts `Origin: null` / missing Origin → CSRF" | Documented intentional: sandboxed iframes without `allow-same-origin` don't send cookies; missing-Origin requests must be non-browser clients without victim cookies. Read the framework's threat model before claiming CSRF. |
| "`child_process.exec` with template-string port → command injection" | If the value reaches `exec` via `parseInt(x, 10)` anywhere upstream, only digits survive. Trace the typing/coercion before claiming injection. |
| "Image fetch follows redirect to private IP → SSRF" | Modern image optimizers recursively re-call the fetch wrapper for each redirect, which re-runs the private-IP check on the new hostname. Read the redirect-handling branch to confirm. Real SSRF here is usually TOCTOU/DNS-rebinding, not redirect-chain. |
| "Cache key omits `searchParams` → poisoning" | Often by design: searchParams are inputs to the response generator (or to `'use cache'`'s explicit hash), not the cache key. Only a bug if a response that varies by searchParams gets stored against a param-less key AND a different user can read it. |
| "`new URL(redirectUrl, base)` + prefix check is bypassable with `..`" | The URL constructor normalizes `..` before the prefix check runs. The check fails on traversal — not exploitable unless the prefix itself is empty/`/`. |
| Local-only CLI tool `execSync(binaryName)` is "RCE" | If exploitation requires PATH manipulation on the developer's own machine, it's not a remote bug. Out of scope for most bounty programs. |
