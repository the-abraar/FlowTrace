#!/usr/bin/env bash
# Fail on template-literal or concatenation assigned into HTML sinks. Allow with trailing `// safe-html: <reason>`.
set -euo pipefail
cd "$(dirname "$0")/.."
sink='(innerHTML|outerHTML)[[:space:]]*\+?=|insertAdjacentHTML[[:space:]]*\(|document\.write(ln)?[[:space:]]*\(|dangerouslySetInnerHTML'
dyn='`[^`]*\$\{|["'"'"'][[:space:]]*\+|\+[[:space:]]*["'"'"']|\+[[:space:]]*[A-Za-z_]'
hits=$(grep -rnE --include='*.html' --include='*.js' --include='*.jsx' --include='*.ts' --include='*.tsx' \
  --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=build --exclude-dir=.git --exclude-dir=.venv --exclude-dir=vendor \
  -e "$sink" . | grep -E "$dyn" | grep -vE '//[[:space:]]*safe-html:' || true)
if [ -n "$hits" ]; then echo "unsafe HTML sink (use textContent/escape, or add '// safe-html: <reason>'):"; echo "$hits"; exit 1; fi
echo "lint-innerhtml: ok"
