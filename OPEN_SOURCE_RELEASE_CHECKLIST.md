# Open-source release checklist (do not publish before review)

Competition material asks the final entry to be open-sourced on Gitee/GitHub and recommends source code, dependencies, deployment/user docs, license explanation, and demo evidence. Treat these as required delivery checks.

- [ ] All team members approve publishing the project code and the selected license.
- [ ] Add the team-approved `LICENSE` file; the current project does not yet select a license.
- [ ] Remove `.env`, all keys/tokens, local databases, logs, private submissions, and unlicensed materials.
- [ ] Inspect `git status` and `git ls-files` before pushing publicly.
- [ ] Audit direct and transitive dependency licenses in the deployment environment; update third-party notices and generate an SBOM if required.
- [ ] Make all demo/synthetic records clearly labelled; do not use placeholder `example.org` links as real sources.
- [ ] Include setup, deployment, user guide, architecture, requirements traceability, tests, and actual demo screenshots/video.
- [ ] Ensure public issue/commit history does not expose secrets accidentally committed earlier; rotate any exposed secret and clean history if needed.
- [ ] Record the public repository URL and release commit/tag.

MIT is one possible option for original project code, but it is not selected here. The team should choose the license deliberately before public release.
