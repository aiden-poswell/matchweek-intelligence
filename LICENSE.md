MIT License

Copyright (c) 2026 Aiden Poswell

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## Scope of this licence

This MIT licence covers this project's own original source code — the Python
forecasting/data pipeline under `src/` and `tests/`, and the React/TypeScript
web application under `web/src/` and its configuration files.

It does **not** cover:

- The underlying football fixture/score data from `openfootball/england`
  (pinned commit `9ee7a0c351805c99cc334478a9bf04b7d0432fec`), which upstream
  publishes under CC0 1.0 Universal
  (<https://github.com/openfootball/england/blob/9ee7a0c351805c99cc334478a9bf04b7d0432fec/LICENSE.md>).
  See `docs/SOURCE_RIGHTS_AND_PROVENANCE.md` for the full provenance record.
- This project's own derived, published research dataset
  (`web/public/data/replays.json` and the reports under `reports/`), which this
  project separately and explicitly dedicates to the public domain under
  CC0 1.0 Universal — see `docs/DERIVED_DATA_LICENCE.md`.

Two CC0-licensed inputs (the upstream data, and this project's own choice to
release its derived dataset under the same terms) do not make this project's
own code CC0; the code's licence is this MIT licence, chosen independently.
