# Publishing to PyPI

## One-time setup

```bash
pip install build twine
```

## Build

```bash
cd constitutional-os
python -m build
# Creates dist/constitutional_os-0.1.0.tar.gz and .whl
```

## Test on TestPyPI first (recommended)

```bash
twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ constitutional-os
```

## Publish to PyPI

```bash
twine upload dist/*
# Enter your PyPI credentials when prompted
# Or use an API token: twine upload -u __token__ -p pypi-... dist/*
```

## After publishing

```bash
pip install constitutional-os
python -c "import constitutional_os; print(constitutional_os.__version__)"
```

## GitHub release

1. Tag the release: `git tag v0.1.0 && git push --tags`
2. Create a GitHub release from the tag
3. Upload the `.tar.gz` and `.whl` from `dist/` as release assets
4. Link to the Zenodo whitepaper in the release notes
