# bracketing-toolkit

The diagram toolchain for the **Biblical Scholar** project: propositional bracketing of Scripture in the Biblearc tradition.

Claude downloads these files at the start of each session, so they don't have to be re-typed from project knowledge every time.

## Files

| File | What it is |
|---|---|
| `bracket_toolkit.py` | The whole toolchain: tree model, layout engine, inline text views, interactive HTML page, and the automated checklist. |
| `passage_template.py` | Starting point for a new passage. Claude copies it, renames it, and fills in the tree and notes. |

## How a session loads them

```bash
curl -sSLO https://raw.githubusercontent.com/muthunag89/bracketing-toolkit/main/bracket_toolkit.py
curl -sSLO https://raw.githubusercontent.com/muthunag89/bracketing-toolkit/main/passage_template.py
```

## How to update a file (in the browser)

When a session fixes the toolkit, Claude hands back the corrected file. To replace the old copy:

1. Open the repository page on GitHub.
2. Click **Add file → Upload files**.
3. Drag the corrected file in. It has the same name, so GitHub replaces the old one.
4. Under **Commit changes**, type a short note (for example, "Fix label collision"), then click **Commit changes**.

GitHub keeps every earlier version under the **History** link on each file, so a bad update can always be undone.

Downloads can serve the old copy for up to about 5 minutes after an update.
