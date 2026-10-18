# Attack surface and taint sinks

Read during Phases 3–4. Grep catalogues for input sources (by language) and the ten dangerous sinks. Always confirm a hit by reading the full function, never from the grep line alone.

## Phase 3 — Attack Surface Mapping

**Goal:** Map every point where attacker-controlled data enters the system. This is the source in taint analysis.

### For JavaScript / TypeScript / Node.js:
```bash
# HTTP route handlers (these receive untrusted input)
grep -rn \
  "app\.\(get\|post\|put\|delete\|patch\|use\|all\)\|router\.\(get\|post\|put\|delete\)\|createServer\|http\.Server" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test\|spec\|\.d\.ts" | head -50

# Server Actions (Next.js) — these are high-value targets per CVE-2025-55182 & 66478
grep -rn "'use server'\|\"use server\"\|registerServerReference\|createActionProxy" \
  --include="*.ts" --include="*.tsx" --include="*.js" \
  . | grep -v "node_modules\|test" | head -30

# Request input access points
grep -rn \
  "req\.body\|req\.params\|req\.query\|req\.headers\|req\.cookies\|request\.json\|request\.formData\|request\.text" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test\|spec" | head -40

# CLI argument input (important for CLI tools like Vercel CLI)
grep -rn "process\.argv\|minimist\|yargs\|commander\|parseArgs" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test" | head -20

# Environment variable usage (can be attacker-controlled in some scenarios)
grep -rn "process\.env\." --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test" | head -20
```

### For Go:
```bash
grep -rn "http\.HandleFunc\|gin\.\|chi\.\|mux\.\|r\.GET\|r\.POST" \
  --include="*.go" . | grep -v "_test.go" | head -40
grep -rn "r\.URL\.Query\|r\.Body\|r\.FormValue\|r\.PathValue\|json\.Decode" \
  --include="*.go" . | grep -v "_test.go" | head -30
```

### For Python:
```bash
grep -rn "@app\.route\|@router\.\|urlpatterns\|@get\|@post" \
  --include="*.py" . | grep -v "test" | head -40
grep -rn "request\.args\|request\.form\|request\.json\|request\.data" \
  --include="*.py" . | grep -v "test" | head -30
```

**Output:** A labeled list of all input sources grouped by type.

---

## Phase 4 — Taint Analysis: Source → Sink

**Goal:** For each input source found in Phase 3, trace whether it reaches a dangerous sink WITHOUT proper sanitization in between. This is how CVE-2025-55182 was found.

### The dangerous sinks to hunt:

**Sink 1: Command Execution (Critical if reached by user input)**
```bash
grep -rn \
  "child_process\|\.exec(\|\.execSync(\|\.spawn(\|\.spawnSync(\|\.execFile(\|shelljs\|execa\|cross-spawn" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test\|spec\|\.d\.ts" | head -30
```
For each match: read the full function. Is the argument string-concatenated from user input? If yes → Critical RCE candidate.

**Sink 2: Dynamic Code Execution**
```bash
grep -rn \
  "\beval(\|\bnew Function(\|vm\.runInThisContext\|vm\.runInNewContext\|vm\.Script\|Function\.prototype\.call\|require(.*\$\|import(.*\$" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test\|spec\|\.d\.ts" | head -20
```

**Sink 3: Prototype Pollution (Critical for frameworks like Next.js)**
```bash
# Object merge functions that accept user input
grep -rn \
  "Object\.assign\|Object\.defineProperty\|deepMerge\|_.merge\|lodash.*merge\|\[.*\]\s*=\s*\|spread\.\.\." \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test\|spec" | head -30

# Prototype access patterns
grep -rn \
  "__proto__\|constructor\.prototype\|\.prototype\[" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test\|spec" | head -20
```
For each merge: does it accept user-controlled keys without filtering `__proto__`, `constructor`, `prototype`?

**Sink 4: File System Access (Path Traversal)**
```bash
grep -rn \
  "fs\.readFile\|fs\.writeFile\|fs\.readdir\|fs\.unlink\|createReadStream\|createWriteStream\|path\.join\|path\.resolve\|fs\.open\|fs\.stat" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test\|spec" | head -30
```
For each: trace back — does a user-supplied string reach `path.join()` or `path.resolve()` without `..` stripping or an allowlist?

**Sink 5: Deserialization (High for frameworks)**
```bash
grep -rn \
  "JSON\.parse\|yaml\.load\|safeLoad\|unserialize\|deserialize\|fromJSON\|msgpack\.decode\|BSON\.deserialize" \
  --include="*.ts" --include="*.js" --include="*.py" \
  . | grep -v "node_modules\|test\|spec" | head -30
```
Check: is `yaml.load` used instead of `yaml.safeLoad`? Is the deserialized result from a network source used without schema validation?

**Sink 6: Server-Side Request Forgery**
```bash
grep -rn \
  "fetch(\|axios\.\|http\.get\|https\.get\|got(\|needle\|request(\|node-fetch" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test\|spec" | head -30
```
For each: does a user-controlled URL reach this fetch call? Are internal IP ranges blocked?

**Sink 7: SQL / NoSQL Injection** *(skip for frameworks that don't directly construct SQL — Next.js, React, build tools rarely have this surface. Run only when the target IS a backend that talks to a DB.)*
```bash
grep -rn \
  "query(\|\.find(\|\.where(\|db\.exec\|\.raw(\|\$where\|mapReduce" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test\|spec" | head -30

# String concatenation in queries — the obvious pattern
grep -rn \
  "\"SELECT\|\"INSERT\|\"UPDATE\|\"DELETE\|\"WHERE\|'SELECT\|'INSERT" \
  --include="*.ts" --include="*.js" --include="*.py" --include="*.go" \
  . | grep -v "node_modules\|test\|spec" | head -20
```

**Sink 8: ReDoS (Regex Denial of Service)** *(low yield on most modern Node frameworks — V8 has linear-time RegExp for non-backtracking patterns. Skip unless target uses regex on hot HTTP paths with user input.)*
```bash
grep -rn "new RegExp\b" --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test\|spec" | head -20
```
For each: is the regex pattern built from user input? Does it contain catastrophic backtracking patterns like `(a+)+`, `(a|a)+`, `(.*a){x}`?

**Sink 9: Template Injection**
```bash
grep -rn \
  "ejs\.render\|handlebars\|nunjucks\|pug\.render\|mustache\|\.template(\|compile(" \
  --include="*.ts" --include="*.js" \
  . | grep -v "node_modules\|test\|spec" | head -20
```

**Sink 10: Hardcoded Secrets**
```bash
grep -rn \
  "api_key\s*=\s*['\"][^'\"]\{8,\}\|apiKey\s*=\s*['\"][^'\"]\{8,\}\|secret\s*=\s*['\"][^'\"]\{8,\}\|password\s*=\s*['\"][^'\"]\{8,\}\|private_key\s*=\|BEGIN RSA\|BEGIN EC\|aws_access_key_id" \
  --include="*.ts" --include="*.js" --include="*.py" --include="*.go" --include="*.yaml" --include="*.yml" \
  . | grep -v "node_modules\|test\|spec\|example\|sample\|\.d\.ts\|PLACEHOLDER\|YOUR_KEY\|TODO" | head -20
```
