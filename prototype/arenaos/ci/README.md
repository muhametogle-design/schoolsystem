# CI / Pages snippets for the prototype

These two files are **ready to use but not installed**, because this workspace's
GitHub connection is an App that may not create or update `.github/workflows/*`:

```
! [remote rejected] (refusing to allow a GitHub App to create or update
   workflow `.github/workflows/ci.yml` without `workflows` permission)
```

A repo admin can either grant that permission to the App, or copy these files into
place — both need two seconds:

```bash
cp prototype/arenaos/ci/pages.yml .github/workflows/pages.yml
git checkout prototype/arenaos/ci/ci.yml -- .github/workflows/ci.yml   # or paste the job below
git add .github/workflows && git commit -m "ci: build the prototype, publish it to Pages"
```

## `pages.yml`

Runs `npm ci && npm run build && npm test` in `prototype/arenaos`, then
`actions/deploy-pages` on `dist/`. Triggers: `workflow_dispatch`, plus pushes to
`main` and `arena/**` touching `prototype/arenaos/**`.

**One manual prerequisite, in the repo UI** (the Actions token is refused:
`POST /repos/…/pages` → 403 *Resource not accessible by integration*):

> Settings → Pages → Source: **GitHub Actions**

Then the site is at `https://muhametogle-design.github.io/schoolsystem/prototype/`.
Until Pages is enabled, the *deploy* job fails with "Pages is not enabled" while the
*build* job still proves the npm path — check it with:

```bash
gh workflow run pages.yml --repo muhametogle-design/schoolsystem --ref <branch>
gh run watch
```

## `ci.yml` — the added job only

If you would rather not take the whole file, this is the entire change to CI:

```yaml
  prototype:
    name: Build and test the standalone prototype
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: prototype/arenaos
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: prototype/arenaos/package-lock.json

      - name: Install, build and test
        run: |
          npm ci --no-audit --no-fund
          npm run build
          npm test

      - name: Fail if the artefacts are missing
        run: |
          test -f dist/index.html
          test -f dist/ArenaOS.html
          test -f dist/ArenaOS.vendor.react-dom.js
```

The `npm test` step matters more here than elsewhere: `src/dist-artifact.test.jsx`
boots the **built** bundle, so a `dist/ArenaOS.html` that renders an empty root
(the `useState` bug this pipeline already caught once) fails the build instead of
failing quietly on a phone.

`pages.yml` also builds with `BASE_PATH=/schoolsystem/prototype/` so asset URLs are
absolute under the Pages subpath; `vite.config.js` defaults to `./` for local `dist/`
copies, and both values were verified from a clean `npm ci` checkout.
