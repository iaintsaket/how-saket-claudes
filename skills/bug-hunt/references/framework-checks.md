# Framework deep dives and auth audit

Read during Phases 5–6, only the sections for frameworks detected in Phase 1.

## Phase 5 — Framework-Specific Deep Dives

Run the relevant section based on what was detected in Phase 1.

### If Next.js detected:

```bash
# Server Actions — primary attack surface per CVE-2025-55182 / 66478
grep -rn "'use server'\|\"use server\"" --include="*.ts" --include="*.tsx" --include="*.js" \
  . | grep -v "node_modules" | head -20

# Flight protocol deserialization — where RCE was found
grep -rn "createFromReadableStream\|createFromFetch\|encodeReply\|decodeReply\|decodeAction\|renderToReadableStream" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test" | head -20

# Source map exposure in production build config
grep -rn "productionBrowserSourceMaps\|sourceMaps\|source-map" \
  --include="next.config.*" --include="*.ts" --include="*.js" \
  . | grep -v "node_modules" | head -10

# __NEXT_DATA__ secret exposure check
grep -rn "__NEXT_DATA__\|getServerSideProps\|getStaticProps" \
  --include="*.ts" --include="*.tsx" --include="*.js" \
  . | grep -v "node_modules\|test" | head -20

# Image optimization SSRF
grep -rn "next/image\|/_next/image\|remotePatterns\|domains" \
  --include="next.config.*" --include="*.ts" --include="*.js" \
  . | grep -v "node_modules" | head -10

# Middleware auth bypass patterns (check-then-use race conditions)
find . -name "middleware.*" | grep -v "node_modules" | xargs cat 2>/dev/null | head -80

# CSRF — Next.js has no built-in CSRF protection
grep -rn "csrf\|CSRF\|xsrf\|XSRF\|SameSite\|sameSite" \
  --include="*.ts" --include="*.js" --include="*.tsx" \
  . | grep -v "node_modules" | head -10
```

Read the content of every Server Action file fully. For each one, ask:
- Is there authorization/authentication checking before the action executes?
- Is deserialized input validated against a schema?
- Can a prototype pollution gadget chain reach `child_process`?

### If Turborepo / Build System detected:

```bash
# Plugin/loader injection surface
grep -rn "plugin\|loader\|transform\|resolveId\|load(" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test" | head -30

# Config files that execute code
find . \( -name "turbo.json" -o -name "*.config.*" \) | grep -v "node_modules\|\.git" | xargs ls -la 2>/dev/null

# Script injection in build pipeline
grep -rn "scripts\.\|exec\|shell\|pipeline" \
  --include="turbo.json" . | grep -v "node_modules" | head -20
```

### If CLI Tool detected (Vercel CLI, etc.):

```bash
# Argument parsing — can arguments inject into shell commands?
grep -rn "parseArgs\|argv\|minimist\|yargs\|commander" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test" | head -20

# Shell command construction from CLI args
grep -rn "exec\|spawn\|execSync" --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test" | head -20
```

### If AI SDK detected:

```bash
# Prompt injection surface
grep -rn "prompt\|messages\|system\|user\|content" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test" | head -30

# Tool/function call abuse
grep -rn "tools\|functions\|tool_use\|function_call\|execute\|runTool" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test" | head -20

# Streaming response injection
grep -rn "stream\|StreamingTextResponse\|createStreamableUI\|readableStream" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test" | head -20
```

---

## Phase 6 — Authorization & Authentication Audit

**Goal:** Missing auth checks are the most common high-severity web bug.

```bash
# Find all auth/permission checking functions
grep -rn \
  "authenticate\|authorize\|checkPermission\|requireAuth\|isAuthenticated\|verifyToken\|validateSession\|getSession\|getUser\|currentUser\|auth()" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test\|spec\|\.d\.ts" | head -40

# JWT handling — look for missing verification or alg:none
grep -rn "jwt\.\|jsonwebtoken\|verify\|decode\|sign(" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test" | head -20

# Routes WITHOUT auth middleware (find the gaps)
grep -rn "router\.\|app\." --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test\|auth\|middleware\|authenticate" | head -30
```

For each sensitive route (state-changing, data-returning), verify: is there an auth check before the business logic executes? Are there routes that call `authenticate()` but then use user-supplied IDs to access resources without confirming ownership?
