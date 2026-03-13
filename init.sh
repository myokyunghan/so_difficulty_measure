#!/usr/bin/env bash
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

read -p "Enter base directory: " BASE_DIR

cat <<EOF > setting_for_sdm/path_setting.py
path_list = {
    "data_root_dir": "$BASE_DIR",
}
EOF

echo "path_setting.py created"
