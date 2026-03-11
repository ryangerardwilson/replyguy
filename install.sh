#!/usr/bin/env bash
set -euo pipefail

APP="replyguy"
REPO="ryangerardwilson/${APP}"
APP_HOME="${HOME}/.${APP}"
INSTALL_DIR="${APP_HOME}/bin"
APP_DIR="${APP_HOME}/app"
VENV_DIR="${APP_HOME}/venv"

usage() {
  cat <<EOF
${APP} Installer

Usage: install.sh [options]

Options:
  -h, --help              Display this help message
  -v                      Print the latest release version
  -v <version>            Install a specific version
  -u, --upgrade           Upgrade to the latest release
  -b, --binary <path>     Install from a local checkout or tarball path
      --no-modify-path    Don't modify shell config files
EOF
}

requested_version=""
show_latest=false
upgrade=false
binary_path=""
no_modify_path=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    -v|--version)
      if [[ -n "${2:-}" && "${2:0:1}" != "-" ]]; then
        requested_version="${2#v}"
        shift 2
      else
        show_latest=true
        shift
      fi
      ;;
    -u|--upgrade)
      upgrade=true
      shift
      ;;
    -b|--binary)
      [[ -n "${2:-}" ]] || { echo "install.sh: -b requires a path" >&2; exit 1; }
      binary_path="$2"
      shift 2
      ;;
    --no-modify-path)
      no_modify_path=true
      shift
      ;;
    *)
      echo "install.sh: unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if $upgrade && [[ -n "$requested_version" || -n "$binary_path" ]]; then
  echo "install.sh: -u cannot be combined with -v <version> or -b" >&2
  exit 1
fi

get_latest_version() {
  curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
    | sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p'
}

if $show_latest; then
  get_latest_version
  exit 0
fi

if $upgrade; then
  latest="$(get_latest_version)"
  if command -v "${APP}" >/dev/null 2>&1; then
    installed="$(${APP} -v 2>/dev/null || true)"
    installed="${installed#v}"
    if [[ -n "$installed" && "$installed" == "$latest" ]]; then
      exit 0
    fi
  fi
  requested_version="$latest"
fi

if [[ -z "$binary_path" && -z "$requested_version" ]]; then
  requested_version="$(get_latest_version)"
fi

mkdir -p "$INSTALL_DIR" "$APP_DIR"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

extract_source() {
  local src_path="$1"
  local out_dir="$2"
  rm -rf "$out_dir"
  mkdir -p "$out_dir"
  if [[ -d "$src_path" ]]; then
    cp -R "$src_path"/. "$out_dir"/
    return 0
  fi
  tar -xzf "$src_path" -C "$tmp_dir"
  local extracted
  extracted="$(find "$tmp_dir" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  [[ -n "$extracted" ]] || { echo "install.sh: failed to extract source archive" >&2; exit 1; }
  cp -R "$extracted"/. "$out_dir"/
}

if [[ -n "$binary_path" ]]; then
  extract_source "$binary_path" "${APP_DIR}/source"
else
  archive_url="https://github.com/${REPO}/archive/refs/tags/v${requested_version}.tar.gz"
  curl -fsSL "$archive_url" -o "${tmp_dir}/${APP}.tar.gz"
  extract_source "${tmp_dir}/${APP}.tar.gz" "${APP_DIR}/source"
fi

if [[ -n "$requested_version" && -f "${APP_DIR}/source/_version.py" ]]; then
  printf '__version__ = "%s"\n' "$requested_version" > "${APP_DIR}/source/_version.py"
fi

python3 -m venv "$VENV_DIR"
"${VENV_DIR}/bin/pip" install --upgrade pip >/dev/null
"${VENV_DIR}/bin/pip" install -r "${APP_DIR}/source/requirements.txt" >/dev/null

cat > "${INSTALL_DIR}/${APP}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
"${VENV_DIR}/bin/python" "${APP_DIR}/source/main.py" "\$@"
EOF
chmod 755 "${INSTALL_DIR}/${APP}"

add_to_path() {
  local config_file="$1"
  local command="$2"
  if grep -Fxq "$command" "$config_file" 2>/dev/null; then
    return 0
  fi
  {
    echo ""
    echo "# ${APP}"
    echo "$command"
  } >> "$config_file"
}

if [[ "$no_modify_path" != "true" && ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
  XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
  current_shell="$(basename "${SHELL:-bash}")"
  case "$current_shell" in
    zsh) config_candidates=("$HOME/.zshrc" "$HOME/.zshenv" "$XDG_CONFIG_HOME/zsh/.zshrc") ;;
    bash) config_candidates=("$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile") ;;
    fish) config_candidates=("$HOME/.config/fish/config.fish") ;;
    *) config_candidates=("$HOME/.profile" "$HOME/.bashrc") ;;
  esac
  config_file=""
  for f in "${config_candidates[@]}"; do
    if [[ -f "$f" ]]; then
      config_file="$f"
      break
    fi
  done
  if [[ -n "$config_file" ]]; then
    if [[ "$current_shell" == "fish" ]]; then
      add_to_path "$config_file" "fish_add_path $INSTALL_DIR"
    else
      add_to_path "$config_file" "export PATH=$INSTALL_DIR:\$PATH"
    fi
  else
    echo "export PATH=$INSTALL_DIR:\$PATH"
  fi
fi

echo "installed: ${INSTALL_DIR}/${APP}"
