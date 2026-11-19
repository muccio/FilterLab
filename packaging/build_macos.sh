#!/usr/bin/env bash
# ==============================================================================
# FilterLab macOS Standalone Application Bundle & DMG Generation Script
# Output: dist/FilterLab.app, dist/FilterLab-1.0.1-macos-<arch>.app.zip & .dmg
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION="1.0.1"

echo "=== FilterLab macOS Standalone Packaging Pipeline ==="
echo "Project Root: ${PROJECT_ROOT}"

OS_NAME="$(uname -s)"
ARCH="$(uname -m)"
echo "Detected Platform: ${OS_NAME} (${ARCH})"

if [ -d "${PROJECT_ROOT}/.venv" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.venv/bin/activate"
fi

if ! command -v pyinstaller &> /dev/null; then
    echo "Error: pyinstaller is not installed in the active environment."
    exit 1
fi

echo "Cleaning previous build and dist artifacts..."
rm -rf "${PROJECT_ROOT}/build" "${PROJECT_ROOT}/dist"

ICON_PATH="${PROJECT_ROOT}/packaging/assets/icon.icns"
if [ ! -f "${ICON_PATH}" ]; then
    python3 "${PROJECT_ROOT}/packaging/generate_assets.py"
fi

echo "Running PyInstaller with filterlab.spec..."
cd "${PROJECT_ROOT}"
pyinstaller --noconfirm --clean "${PROJECT_ROOT}/packaging/filterlab.spec"

APP_PATH="${PROJECT_ROOT}/dist/FilterLab.app"
if [ "${OS_NAME}" != "Darwin" ]; then
    echo "Non-macOS environment (${OS_NAME}); PyInstaller finished."
    exit 0
fi

if [ ! -d "${APP_PATH}" ]; then
    echo "Error: FilterLab.app was not generated in dist/!"
    exit 1
fi

RESOURCES_DIR="${APP_PATH}/Contents/Resources"
PLIST_PATH="${APP_PATH}/Contents/Info.plist"
mkdir -p "${RESOURCES_DIR}"
cp -f "${ICON_PATH}" "${RESOURCES_DIR}/icon.icns"

if command -v plutil &> /dev/null && [ -f "${PLIST_PATH}" ]; then
    echo "Validating Info.plist via plutil..."
    plutil -lint "${PLIST_PATH}"
fi

echo "Verifying compiled bundle (--check-build)..."
"${APP_PATH}/Contents/MacOS/FilterLab" --check-build

echo "Creating zipped .app archive..."
APP_ZIP="FilterLab-${VERSION}-macos-${ARCH}.app.zip"
(cd "${PROJECT_ROOT}/dist" && ditto -c -k --sequesterRsrc --keepParent "FilterLab.app" "${APP_ZIP}")

echo "Generating FilterLab DMG using hdiutil..."
DMG_STAGING="${PROJECT_ROOT}/dist/dmg_staging"
rm -rf "${DMG_STAGING}"
mkdir -p "${DMG_STAGING}"
cp -R "${APP_PATH}" "${DMG_STAGING}/"
ln -s /Applications "${DMG_STAGING}/Applications"

DMG_OUTPUT="${PROJECT_ROOT}/dist/FilterLab-${VERSION}-macos-${ARCH}.dmg"
rm -f "${DMG_OUTPUT}"

hdiutil create \
    -volname "FilterLab" \
    -srcfolder "${DMG_STAGING}" \
    -ov \
    -format UDZO \
    "${DMG_OUTPUT}"

rm -rf "${DMG_STAGING}"

echo "========================================================"
echo " macOS Build Completed Successfully!"
echo " App Bundle: ${APP_PATH}"
echo " App Zip:    ${PROJECT_ROOT}/dist/${APP_ZIP}"
echo " Disk Image: ${DMG_OUTPUT}"
echo "========================================================"
