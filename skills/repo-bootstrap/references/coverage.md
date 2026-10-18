# Coverage gates by stack

Put the threshold in the project config as well as in CI, so `make test` (or its equivalent) fails locally in the same way. Measure **line coverage of source code only**: tests, generated code and vendored code don't count. `scripts/verify_repo.py` looks for the markers shown below.

## Python (pytest-cov)

`pyproject.toml`:

```toml
[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "ruff"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.coverage.run]
source = ["src"]          # or the package name; without it the tests count towards coverage
branch = true

[tool.coverage.report]
fail_under = 80
show_missing = true
```

The CI also passes `--cov-fail-under=$COVERAGE_MIN`. When the two disagree, the stricter one fails first.

## Node (Jest)

`jest.config.js`:

```js
module.exports = {
  collectCoverageFrom: ["src/**/*.{js,ts,jsx,tsx}", "!src/**/*.d.ts"],
  coverageThreshold: { global: { lines: 80, statements: 80, branches: 80, functions: 80 } },
};
```

## Node (Vitest)

`vitest.config.ts`. This needs `@vitest/coverage-v8` as a dev dependency:

```ts
import { defineConfig } from "vitest/config";
export default defineConfig({
  test: {
    coverage: {
      provider: "v8",
      include: ["src/**"],
      thresholds: { lines: 80, statements: 80, branches: 80, functions: 80 },
    },
  },
});
```

`npm test -- --coverage` only works when the `test` script calls jest or vitest directly (for example `"test": "vitest run"`). If it chains other commands, add `"test:coverage"` and change the CI step to `npm run test:coverage`.

## Go

There's no config file for this. The CI step parses `go tool cover -func` output and compares it with `COVERAGE_MIN`. Since Go 1.22, packages without test files count as 0%, so keep `main` packages thin.

## Rust (cargo-llvm-cov)

`--fail-under-lines $COVERAGE_MIN` is the gate. Locally: `cargo install cargo-llvm-cov`, then `cargo llvm-cov --fail-under-lines 80`.

## Java (Gradle, JaCoCo)

`build.gradle.kts`:

```kotlin
plugins { java; jacoco }

tasks.test { useJUnitPlatform(); finalizedBy(tasks.jacocoTestReport) }
tasks.jacocoTestCoverageVerification {
    dependsOn(tasks.test)
    violationRules { rule { limit { counter = "LINE"; minimum = "0.80".toBigDecimal() } } }
}
tasks.check { dependsOn(tasks.jacocoTestCoverageVerification) }
```

Commit the Gradle wrapper (`gradlew`, `gradle/wrapper/*`) and make `gradlew` executable (`git update-index --chmod=+x gradlew`).

## Java (Maven, JaCoCo)

`pom.xml` → `<build><plugins>`:

```xml
<plugin>
  <groupId>org.jacoco</groupId>
  <artifactId>jacoco-maven-plugin</artifactId>
  <version><!-- current release --></version>
  <executions>
    <execution><goals><goal>prepare-agent</goal></goals></execution>
    <execution><id>report</id><phase>verify</phase><goals><goal>report</goal></goals></execution>
    <execution>
      <id>check</id>
      <goals><goal>check</goal></goals>
      <configuration>
        <rules><rule><element>BUNDLE</element><limits><limit>
          <counter>LINE</counter><value>COVEREDRATIO</value><minimum>0.80</minimum>
        </limit></limits></rule></rules>
      </configuration>
    </execution>
  </executions>
</plugin>
```

## Other stacks

Use the stack's native coverage tool, make CI fail below `COVERAGE_MIN` (80), and keep the job named `ci`. If the tool has no built-in gate, parse its total the way the Go template does.
