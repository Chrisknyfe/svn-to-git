#!/bin/bash

# Example of how to clone a remote svn repository locally

svnadmin create localsvn
echo '#!/bin/bash' > localsvn/hooks/pre-revprop-change
chmod +x localsvn/hooks/pre-revprop-change
svnsync init file:///home/chrisknyfe/migration/localsvn https://pl3.projectlocker.com/Team/project/svn/
svnsync sync file:///home/chrisknyfe/migration/localsvn

