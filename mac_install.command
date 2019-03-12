# Script for installing RCL Cleaner plugin for QGIS on Mac OS/X

# Path variables
qgis_user_dir=~/.qgis2
rcl_plugin_dir=$qgis_user_dir/python/plugins/RoadNetworkCleaner

# Make sure QGIS is installed
if [ ! -d "$qgis_user_dir" ]; then
	echo "ERROR: QGIS not found."
	exit 1
fi

# Remove previously installed plugin
if [ -d "$rcl_plugin_dir" ]; then
	echo "Removing currently installed RCL Cleaner QGIS plugin..."
	rm -rf "$rcl_plugin_dir"
	if [ $? -ne 0 ]; then
		echo "ERROR: Couldn't remove currently installed RCL Cleaner QGIS plugin."
		echo "Please close QGIS if it is running, and then try installing again."
		exit 1
	fi
fi

if [ ! -d "$rcl_plugin_dir" ]; then
	mkdir -p "$rcl_plugin_dir"
	if [ $? -ne 0 ]; then
		echo "ERROR: Couldn√'t create directory '$rcl_plugin_dir'"
		exit 1
	fi
fi

echo "Copying RCL Cleaner QGIS plugin to QGIS plugin directory..."
cp -r RCL-topology-cleaner/* "$rcl_plugin_dir/"
if [ $? -ne 0 ]; then
	echo "ERROR: Couldn't copy 'RCL-topology-cleaner' to '$rcl_plugin_dir/'"
	exit 1
fi

echo "RCL Cleaner QGIS plugin was successfully installed!"
echo "Please see readme.txt for instructions on how to enable it."
exit 0
