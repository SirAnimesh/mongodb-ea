# Lima on Fedora
#
# Lima is not currently packaged in the official Fedora repos. 
# The cleanest solution is to grab the pre-built binary from their GitHub releases.
#
# This script extracts the lima binary into /usr/local.
# Check the Lima release page for latest version number - https://github.com/lima-vm/lima/releases

LIMA_VERSION="2.1.3"
OS="Linux"
ARCH="x86_64"

curl -fsSL "https://github.com/lima-vm/lima/releases/download/v${LIMA_VERSION}/lima-${LIMA_VERSION}-${OS}-${ARCH}.tar.gz" -o lima.tar.gz

sudo tar -C /usr/local -xzf lima.tar.gz

rm lima.tar.gz
