# TypeScript Tooling Quick Reference

> Tools: pnpm, eslint, prettier, vitest, tsc | Node 20+, TypeScript 5+
> Last verified: 2026-02-04 from official docs

## pnpm (Package Manager)

> Faster, disk-efficient alternative to npm/yarn

| Task | Command |
|------|---------|
| Init project | `pnpm init` |
| Add dependency | `pnpm add package` |
| Add dev dependency | `pnpm add -D package` |
| Add exact version | `pnpm add -E package` |
| Add to workspace root | `pnpm add -w package` |
| Remove | `pnpm remove package` |
| Install all | `pnpm install` |
| Update packages | `pnpm update` |
| Run script | `pnpm run script` or `pnpm script` |
| Audit vulnerabilities | `pnpm audit` |
| Show outdated | `pnpm outdated` |

### package.json Scripts
```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "test": "vitest",
    "test:run": "vitest run",
    "test:coverage": "vitest --coverage",
    "lint": "eslint .",
    "lint:fix": "eslint . --fix",
    "format": "prettier --write .",
    "format:check": "prettier --check .",
    "typecheck": "tsc --noEmit"
  }
}
```

## TypeScript (tsc)

| Task | Command |
|------|---------|
| Type check | `pnpm typecheck` or `tsc --noEmit` |
| Build | `tsc` |
| Watch mode | `tsc --watch` |
| Init config | `tsc --init` |

### tsconfig.json (Strict)
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist",
    "declaration": true,
    "isolatedModules": true
  },
  "include": ["src"],
  "exclude": ["node_modules", "dist"]
}
```

### Common Type Patterns
```typescript
// Union types
type Status = "pending" | "active" | "done";

// Optional properties
interface User {
  id: string;
  name: string;
  email?: string;  // optional
}

// Readonly
interface Config {
  readonly apiUrl: string;
}

// Generics
function first<T>(arr: T[]): T | undefined {
  return arr[0];
}

// Result type pattern
type Result<T, E = Error> =
  | { success: true; data: T }
  | { success: false; error: E };

// Discriminated unions (state machines)
type LoadingState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: Error };

// Utility types
type PartialUser = Partial<User>;      // all optional
type RequiredUser = Required<User>;    // all required
type UserName = Pick<User, "name">;    // subset
type NoEmail = Omit<User, "email">;    // exclude
type UserKeys = keyof User;            // "id" | "name" | "email"

// Type guards
function isUser(obj: unknown): obj is User {
  return typeof obj === "object" && obj !== null && "id" in obj;
}

// Const assertion for literals
const status = "active" as const;  // type: "active", not string
```

## ESLint (Flat Config)

| Task | Command |
|------|---------|
| Lint | `pnpm lint` |
| Lint + fix | `pnpm lint:fix` |

### eslint.config.js (Flat Config - ESLint 9+)
```javascript
import eslint from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        project: true,
      },
    },
    rules: {
      "@typescript-eslint/no-unused-vars": ["error", {
        argsIgnorePattern: "^_",
        varsIgnorePattern: "^_"
      }],
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
  {
    ignores: ["dist/", "node_modules/", "*.config.*"],
  }
);
```

## Prettier

| Task | Command |
|------|---------|
| Format all | `pnpm format` |
| Check only | `pnpm format:check` |

### .prettierrc
```json
{
  "semi": true,
  "singleQuote": false,
  "tabWidth": 2,
  "trailingComma": "es5",
  "printWidth": 100
}
```

### .prettierignore
```
dist/
node_modules/
pnpm-lock.yaml
```

## Vitest

> Requires: Vite >=6.0.0, Node >=20.0.0

| Task | Command |
|------|---------|
| Run (watch mode) | `pnpm test` |
| Run once | `vitest run` |
| Coverage | `vitest --coverage` |
| UI mode | `vitest --ui` |
| Specific file | `vitest src/utils.test.ts` |
| Update snapshots | `vitest -u` |

### vitest.config.ts
```typescript
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",  // or "jsdom", "happy-dom"
    include: ["src/**/*.test.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      exclude: ["node_modules/", "dist/"],
    },
  },
});
```

### Test Patterns
```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

describe("UserService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should create user", async () => {
    const user = await createUser({ name: "Test" });
    expect(user.name).toBe("Test");
  });

  it("should throw on invalid input", () => {
    expect(() => createUser({})).toThrow("Name required");
  });

  it("should match snapshot", () => {
    const result = formatUser(user);
    expect(result).toMatchSnapshot();
  });
});
```

### Mocking
```typescript
// Mock a module
vi.mock("./api", () => ({
  fetchUser: vi.fn().mockResolvedValue({ id: 1, name: "Mock" }),
}));

// Spy on a method
const spy = vi.spyOn(console, "log");
doSomething();
expect(spy).toHaveBeenCalledWith("expected");
spy.mockRestore();

// Mock timers
vi.useFakeTimers();
setTimeout(() => callback(), 1000);
vi.advanceTimersByTime(1000);
expect(callback).toHaveBeenCalled();
vi.useRealTimers();
```

### Async Testing
```typescript
it("should fetch data", async () => {
  const data = await fetchData();
  expect(data).toEqual({ id: 1 });
});

it("should reject with error", async () => {
  await expect(failingFetch()).rejects.toThrow("Network error");
});
```

## Gotchas

- Use `pnpm` not `npm` for faster, disk-efficient installs
- ESLint flat config (`eslint.config.js`) is the new standard in ESLint 9+
- `strict: true` in tsconfig catches most issues
- Vitest API is mostly compatible with Jest
- Use `as const` for literal types: `const x = "foo" as const`
- Avoid `any` - use `unknown` and narrow with type guards
- `noUncheckedIndexedAccess` catches array/object access bugs

## Project Conventions

- Strict TypeScript config (`strict: true`)
- ESLint + Prettier (no conflicts with eslint-config-prettier)
- Tests co-located: `foo.ts` → `foo.test.ts`
- Types in separate `types.ts` files when shared
- Run `pnpm typecheck && pnpm lint && pnpm test` before committing
- Run `./scripts/verify.sh` for full verification
