# Script for uninstalling RCL Cleaner plugin for QGIS on Mac OS/X

# Path variables
rcl_plugin_dir=~/.qgis2/python/plugins/RoadNetworkCleaner

# Make sure QGIS is installed
if [ ! -d "$rcl_plugin_dir" ]; then
	echo "RCL Cleaner QGIS plugin not found."
	exit 1
fi

rm -rf "$rcl_plugin_dir"
if [ $? -ne 0 ]; then
	echo "ERROR: Couldn't remove currently installed RCL Cleaner QGIS plugin."
	echo "Please close QGIS if it is running, and then try again."
	exit 1
fi

echo "RCL Cleaner QGIS plugin was successfully uninstalled."
