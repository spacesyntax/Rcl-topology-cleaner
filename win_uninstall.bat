@ECHO OFF

set rcl_plugin_dir=%UserProfile%\.qgis2\python\plugins\RoadNetworkCleaner

IF NOT EXIST "% rcl_plugin_dir%" (
	ECHO RCL Cleaner QGIS plugin not found.
	PAUSE
	EXIT
)

rmdir "%rcl_plugin_dir%" /s /q
IF EXIST "% rcl_plugin_dir%" (
	ECHO ERROR: Couldn't remove currently installed RCL Cleaner QGIS plugin.
	ECHO Please close QGIS if it is running, and then try again.
	PAUSE
	EXIT
)

ECHO RCL Cleaner QGIS plugin was successfully uninstalled.
ECHO.
PAUSE