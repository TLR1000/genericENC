# genericENC
Collection of scripts for ENC or IENC chart processing using python


# cl_list_buoys_in_ENC.py - List all buoys in the ENC
This script is designed to extract buoy data from Electronic Navigational Chart (ENC) files using the GDAL/OGR library. The script processes ENC files to identify and extract various attributes of buoys, such as their type, position, color, shape, and associated light characteristics. The extracted data is then saved to a text file and printed to the console.
The script sets up logging to both a file (enc_extraction.log) and the console, with a specific format for log messages.

### BuoyExtractor Class:  
This class encapsulates the functionality for extracting buoy data from ENC files.  
Attributes:   
BUOY_OBJECT_CLASSES: List of buoy object types defined in S-57/IENC standards.  
LIGHT_OBJECTS and TOPMARK_OBJECTS: Lists of related object types for buoys.   
INLAND_BUOY_SYSTEMS: Definitions for inland buoy systems.   

### Noteable Methods:   
process_layer(self, dataset, layer): Processes a single layer in the ENC file to extract buoy features.   
extract_buoy_data(self, dataset, feature): Extracts data for a specific buoy feature.   
get_field_value(self, feature, field_name, default=''): Helper function to get field values from a feature.   
get_color_description(self, feature): Extracts and describes the color of a buoy.   
get_buoy_shape(self, feature): Extracts and describes the shape of a buoy.   
get_topmark_shape(self, feature): Extracts and describes the shape of a topmark.   
get_light_character(self, feature): Extracts and describes the light characteristics of a buoy.   
find_related_objects(self, dataset, feature, object_classes): Finds objects related to a buoy.   
determine_buoy_system(self, feature): Determines if the buoy is part of an inland or offshore system.   
 
The script is executed by calling the main() function if the script is run as the main module.  
Usage:  
The script is intended to be run from the command line.   
It processes a specific ENC file and outputs the extracted buoy data to a specified directory.   
The output includes detailed information about each buoy, such as its type, position, color, shape, and associated light characteristics.  
