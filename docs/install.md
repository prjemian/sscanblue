# Install

Install both `sscanblue` and `nbs-viewer`.

## Activate Python environment

If you need to create a new Python environment:

```bash
conda create -n sscanblue python
```

Then, activate it:

```bash
conda activate sscanblue
```

## Checkout source

```bash
git clone https://github.com/BCDA-APS/sscanblue
cd sscanblue
```

## Install `sscanblue`

```bash
python -m pip install .
```

Use the editable option keyword, if desired: `python -m pip install -e .`

## Install `nbs-viewer`

FIXME: Needs to be in a separate environment to avoid databroker version conflicts.

```bash
python -m pip install git+https://github.com/xraygui/nbs-viewer
```
