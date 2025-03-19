import os
import sys
from osgeo import ogr, gdal
import logging
from datetime import datetime

# Logger configuratie
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("enc_extraction.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ENC_Extraction")

class BuoyExtractor:
    """
    Klasse voor het extraheren van boeikenmerken uit ENC/IENC-bestanden met GDAL/OGR
    """
    
    # Definities van boeitype objecten in S-57/IENC
    BUOY_OBJECT_CLASSES = [
        'BOYLAT',  # Laterale boei
        'BOYCAR',  # Kardinale boei
        'BOYISD',  # Geïsoleerd gevaar boei
        'BOYSAW',  # Veilig water boei
        'BOYSPP',  # Speciale doeleinden boei
        'BOYINB',  # Binnenvaart boei
    ]
    
    # Gekoppelde objecttypes voor boeien
    LIGHT_OBJECTS = ['LIGHTS', 'LITFLT']  # Lichten, drijvende lichten
    TOPMARK_OBJECTS = ['TOPMAR']  # Topmarkeringen
    
    # Definities voor binnenvaartbetonning (IENC specifiek)
    INLAND_BUOY_SYSTEMS = {
        'catlam': {  # Categorie laterale markering
            1: 'Stuurboord',
            2: 'Bakboord',
            3: 'Voorkeursvaarwater rechts',
            4: 'Voorkeursvaarwater links',
        },
        'marsys': {  # Betonningssysteem
            1: 'IALA A',
            2: 'IALA B',
            10: 'Binnenvaart',
            11: 'CEVNI',
        }
    }
    
    def __init__(self, enc_file, output_dir):
        """
        Initialiseer de extractor met het pad naar het ENC-bestand en de output map
        
        Args:
            enc_file (str): Pad naar het ENC-bestand
            output_dir (str): Pad naar de output map
        """
        self.enc_file = enc_file
        self.output_dir = output_dir
        self.buoy_data = []
    
    def extract_buoys(self):
        """
        Extraheert boeigegevens uit het ENC-bestand
        """
        try:
            logger.info(f"Verwerken van {self.enc_file}")
            self.process_enc_file()
        except Exception as e:
            logger.error(f"Fout bij verwerken van {self.enc_file}: {str(e)}")
    
    def process_enc_file(self):
        """
        Verwerkt het ENC-bestand om boeigegevens te extraheren
        """
        # Registreer het S-57 stuurprogramma
        ogr.RegisterAll()
        driver = ogr.GetDriverByName('S57')
        
        if driver is None:
            raise Exception("S57 driver niet gevonden. Controleer of GDAL/OGR correct is geïnstalleerd.")
        
        # Open het ENC-bestand met OGR
        try:
            # Geef S-57 specifieke opties aan GDAL
            #options = ["LNAM_REFS=ON", "RETURN_PRIMITIVES=ON", "RETURN_LINKAGES=ON"]
            #dataset = driver.Open(self.enc_file, 0, options)
            # Open the file with options
            dataset = gdal.OpenEx(self.enc_file, 
                                gdal.OF_VECTOR, 
                                open_options=["LNAM_REFS=ON", "RETURN_PRIMITIVES=ON", "RETURN_LINKAGES=ON"])
            
            if dataset is None:
                raise Exception(f"Kon ENC-bestand niet openen: {self.enc_file}")
            
            # Doorloop alle lagen in het dataset
            layer_count = dataset.GetLayerCount()
            logger.info(f"Aantal lagen in dataset: {layer_count}")
            
            # Zoek naar boeiobjecten in alle lagen
            for i in range(layer_count):
                layer = dataset.GetLayerByIndex(i)
                layer_name = layer.GetName()
                
                # Alleen doorgaan als deze laag een van de boeiobjecten kan bevatten
                if layer_name in self.BUOY_OBJECT_CLASSES:
                    logger.info(f"Verwerken van laag: {layer_name}")
                    self.process_layer(dataset, layer)
            
            dataset = None  # Sluit het dataset
            
        except Exception as e:
            logger.error(f"Fout bij verwerken van {self.enc_file}: {str(e)}")
    
    def process_layer(self, dataset, layer):
        """
        Verwerkt een enkele laag om boeiobjecten te extraheren
        
        Args:
            dataset (ogr.DataSource): OGR dataset
            layer (ogr.Layer): OGR laag
        """
        # Reset de leesstrategie om alle features te lezen
        layer.ResetReading()
        
        # Lees alle features in de laag
        feature = layer.GetNextFeature()
        while feature is not None:
            # Controleer of dit feature een boei is
            obj_class = feature.GetField('OBJL') if feature.IsFieldSet('OBJL') else None
            primitive = feature.GetField('PRIM') if feature.IsFieldSet('PRIM') else None
            
            if obj_class and primitive:
                buoy_data = self.extract_buoy_data(dataset, feature)
                if buoy_data:
                    self.buoy_data.append(buoy_data)
            
            # Ga naar de volgende feature
            feature = layer.GetNextFeature()
    
    def extract_buoy_data(self, dataset, feature):
        """
        Extraheert gegevens van een specifieke boei
        
        Args:
            dataset (ogr.DataSource): OGR dataset
            feature (ogr.Feature): OGR feature
            
        Returns:
            dict: Dictionary met boeikenmerken
        """
        try:
            # Basisgegevens van de boei
            feature_id = feature.GetField('LNAM') if feature.IsFieldSet('LNAM') else feature.GetFID()
            obj_class = feature.GetField('OBJL') if feature.IsFieldSet('OBJL') else None
            
            # Zet numerieke objectklasse om naar string indien nodig
            if isinstance(obj_class, int):
                # Vertaal objectklassenummers naar namen indien beschikbaar
                obj_class_map = {
                    17: 'BOYLAT',
                    18: 'BOYCAR',
                    19: 'BOYISD',
                    20: 'BOYSAW',
                    22: 'BOYSPP',
                    # Voeg hier meer toe indien nodig
                }
                obj_class = obj_class_map.get(obj_class, f"Unknown({obj_class})")
            
            # Controleer of er positie-informatie is
            geometry = feature.GetGeometryRef()
            if not geometry:
                logger.warning(f"Boei {feature_id} heeft geen positie")
                return None
            
            # Extract coördinaten (lat/lon)
            if geometry.GetGeometryType() == ogr.wkbPoint:
                lon = geometry.GetX()
                lat = geometry.GetY()
            else:
                # Voor andere geometrietypen zoals lijnen of polygonen, gebruik het centroid
                centroid = geometry.Centroid()
                lon = centroid.GetX()
                lat = centroid.GetY()
            
            # Object naam ophalen (kan verschillen per implementatie)
            name = ""
            if feature.IsFieldSet('OBJNAM'):
                name = feature.GetField('OBJNAM')
            
            # Boei basisinformatie
            buoy_info = {
                'id': feature_id,
                'type': obj_class,
                'name': name,
                'lon': lon,
                'lat': lat,
                'color': self.get_color_description(feature),
                'shape': self.get_buoy_shape(feature),
                'category': self.get_field_value(feature, 'CATCAM', ''),  # Categorie kardinale markering
                'lateral_mark': self.get_field_value(feature, 'CATLAM', ''),  # Categorie laterale markering
                'system': self.get_field_value(feature, 'MARSYS', ''),  # Betonningssysteem
            }
            
            # Bepaal of dit binnengaats of buitengaats betonning is
            buoy_info['betonning_type'] = self.determine_buoy_system(feature)
            
            # Zoek naar gekoppelde objecten voor deze boei
            # 1. Topmarkering
            topmarks = self.find_related_objects(dataset, feature, self.TOPMARK_OBJECTS) 
            if topmarks:
                topmark = topmarks[0]  # Neem de eerste topmarkering
                buoy_info['topmark_shape'] = self.get_topmark_shape(topmark)
                buoy_info['topmark_color'] = self.get_color_description(topmark)
            
            # 2. Lichtkarakteristiek
            lights = self.find_related_objects(dataset, feature, self.LIGHT_OBJECTS)
            if lights:
                light = lights[0]  # Neem het eerste licht
                buoy_info['light_character'] = self.get_light_character(light)
                buoy_info['light_color'] = self.get_color_description(light)
                buoy_info['light_period'] = self.get_field_value(light, 'SIGPER', '')
                buoy_info['light_group'] = self.get_field_value(light, 'SIGGRP', '')
                buoy_info['light_range'] = self.get_field_value(light, 'VALNMR', '')
                
            # Controleer op ontbrekende velden
            self.check_missing_fields(buoy_info)
            
            return buoy_info
            
        except Exception as e:
            logger.error(f"Fout bij het verwerken van boei: {str(e)}")
            return None
    
    def get_field_value(self, feature, field_name, default=''):
        """Helper functie om veldwaarden op te halen"""
        if feature.IsFieldSet(field_name):
            return feature.GetField(field_name)
        return default
    
    def get_color_description(self, feature):
        """
        Extraheert de kleur van een object
        
        Args:
            feature (ogr.Feature): OGR feature
            
        Returns:
            str: Beschrijving van de kleur
        """
        colors = []
        if feature.IsFieldSet('COLOUR'):
            colors = feature.GetField('COLOUR')
            # Log voor debugging
            logger.debug(f"Kleurwaarde uit feature: {colors}, type: {type(colors)}")
        
        color_pattern = ''
        if feature.IsFieldSet('COLPAT'):
            color_pattern = feature.GetField('COLPAT')
        
        if not colors:
            return ''
        
        # Kleurcode naar beschrijving omzetten
        color_map = {
            1: 'wit', 
            2: 'zwart', 
            3: 'rood', 
            4: 'groen', 
            5: 'blauw',
            6: 'geel', 
            7: 'grijs', 
            8: 'bruin', 
            9: 'amber', 
            10: 'violet',
            11: 'oranje', 
            12: 'magenta', 
            13: 'roze'
        }
        
        # Patrooncode naar beschrijving
        pattern_map = {
            1: 'horizontaal gestreept',
            2: 'verticaal gestreept',
            3: 'diagonaal gestreept',
            4: 'geruit',
            5: 'geblokt'
        }
        
        # Converteer kleurcodes naar namen, behandel zowel enkele waarden als lijsten
        color_names = []
        
        # Behandel de verschillende mogelijke formaten van colors
        if isinstance(colors, list):
            # Als colors al een lijst is
            color_list = colors
        elif isinstance(colors, (int, float)):
            # Als colors een enkele numerieke waarde is
            color_list = [int(colors)]
        else:
            # Als colors een string is of iets anders, probeer het op te splitsen
            try:
                if isinstance(colors, str) and ',' in colors:
                    color_list = [int(c.strip()) for c in colors.split(',')]
                else:
                    color_list = [int(colors)]
            except (ValueError, TypeError):
                logger.warning(f"Kon kleurcode niet verwerken: {colors}")
                return ''
        
        # Converteer elke code naar een kleurnaam
        for color_code in color_list:
            if color_code in color_map:
                color_names.append(color_map[color_code])
            else:
                color_names.append(f"onbekend({color_code})")
        
        color_str = '/'.join(color_names)
        
        # Voeg patroon toe indien aanwezig
        if color_pattern:
            try:
                pattern_code = int(color_pattern)
                if pattern_code in pattern_map:
                    color_str += f" ({pattern_map[pattern_code]})"
            except (ValueError, TypeError):
                pass
                
        return color_str
    
    def get_buoy_shape(self, feature):
        """
        Extraheert de vorm van een boei
        
        Args:
            feature (ogr.Feature): OGR feature
            
        Returns:
            str: Beschrijving van de vorm
        """
        shape = ''
        if feature.IsFieldSet('BOYSHP'):
            shape_code = feature.GetField('BOYSHP')
            
            # Vormcode naar beschrijving
            shape_map = {
                1: 'ton',
                2: 'cilinder',
                3: 'kegel',
                4: 'bol',
                5: 'sparbaken',
                6: 'paal',
                7: 'boei met lantaarn',
                8: 'tol'
            }
            
            try:
                shape_code = int(shape_code)
                if shape_code in shape_map:
                    shape = shape_map[shape_code]
            except ValueError:
                pass
        
        return shape
    
    def get_topmark_shape(self, feature):
        """
        Extraheert de vorm van een topmarkering
        
        Args:
            feature (ogr.Feature): OGR feature
            
        Returns:
            str: Beschrijving van de vorm
        """
        shape = ''
        if feature.IsFieldSet('TOPSHP'):
            shape_code = feature.GetField('TOPSHP')
            
            # Vormcode naar beschrijving
            shape_map = {
                1: 'kegel omhoog',
                2: 'kegel omlaag',
                3: 'twee kegels puntomhoog',
                4: 'twee kegels puntomlaag',
                5: 'twee kegels punten naar elkaar',
                6: 'twee kegels punten van elkaar',
                7: 'bol',
                8: 'kruis',
                9: 'x-vorm',
                10: 'kubus',
                11: 'cilinder',
                12: 'bord',
                13: 'ruit',
                14: 'rechthoek',
                15: 'bezemstek',
                16: 'bezem omlaag',
                17: 'bezem omhoog',
                18: 'driehoek',
                19: 'T-vorm',
                20: 'cirkel',
                21: 'halve bol',
                22: 'tonvormig',
                23: 'bol over rom',
                24: 'ruit over bol',
                25: 'cirkelschijf',
                26: 'twee bollen',
                27: 'twee rechthoekige borden',
                28: 'diagonaal bord',
                29: 'vierkant over driehoek'
            }
            
            try:
                shape_code = int(shape_code)
                if shape_code in shape_map:
                    shape = shape_map[shape_code]
            except ValueError:
                pass
        
        return shape
    
    def get_light_character(self, feature):
        """
        Extraheert de lichtkarakteristiek
        
        Args:
            feature (ogr.Feature): OGR feature
            
        Returns:
            str: Beschrijving van de lichtkarakteristiek
        """
        character = ''
        if feature.IsFieldSet('LITCHR'):
            char_code = feature.GetField('LITCHR')
            
            # Karaktercode naar beschrijving
            char_map = {
                1: 'vast',
                2: 'groepschitterend',
                3: 'flikkerlicht',
                4: 'onderbroken',
                5: 'schitterlicht',
                6: 'ultrasnel flikkerlicht',
                7: 'isofase',
                8: 'occulterende',
                9: 'langzaam flikkerlicht',
                10: 'morse code',
                11: 'ononderbroken ultrasnel flikkerlicht',
                12: 'vast schitterlicht',
                13: 'vast groepschitterlicht',
                14: 'langzaam onderbroken',
                15: 'onderbroken groepslicht',
                16: 'occulterende groepslicht',
                17: 'onderbroken ultrasnel flikkerlicht',
                18: 'langzaam flikkerende groepslicht',
                19: 'flikkerende groepslicht',
                20: 'groep occulterende',
                25: 'kort-lang schitterlicht',
                26: 'ultrasnel groep flikkerlicht',
                27: 'display licht'
            }
            
            try:
                char_code = int(char_code)
                if char_code in char_map:
                    character = char_map[char_code]
            except ValueError:
                pass
        
        return character
    
    def find_related_objects(self, dataset, feature, object_classes):
        """
        Zoekt naar objecten die gerelateerd zijn aan de boei
        
        Args:
            dataset (ogr.DataSource): OGR dataset
            feature (ogr.Feature): OGR feature van de boei
            object_classes (list): Lijst met objectklassen om naar te zoeken
            
        Returns:
            list: Lijst met gerelateerde features
        """
        related_objects = []
        
        # Haal de boeipositie op
        boei_geom = feature.GetGeometryRef()
        if not boei_geom:
            return related_objects
            
        boei_x = boei_geom.GetX() if boei_geom.GetGeometryType() == ogr.wkbPoint else boei_geom.Centroid().GetX()
        boei_y = boei_geom.GetY() if boei_geom.GetGeometryType() == ogr.wkbPoint else boei_geom.Centroid().GetY()
        
        # Doorzoek alle lagen in het dataset op zoek naar gerelateerde objecten
        layer_count = dataset.GetLayerCount()
        
        for i in range(layer_count):
            layer = dataset.GetLayerByIndex(i)
            layer_name = layer.GetName()
            
            # Controleer of deze laag een van de gezochte objectklassen bevat
            if layer_name not in object_classes:
                continue
                
            # Reset de leesstrategie
            layer.ResetReading()
            
            # Doorloop alle features in de laag
            related_feature = layer.GetNextFeature()
            while related_feature is not None:
                # Controleer op ruimtelijke relatie (objecten op dezelfde positie)
                related_geom = related_feature.GetGeometryRef()
                
                if related_geom:
                    related_x = related_geom.GetX() if related_geom.GetGeometryType() == ogr.wkbPoint else related_geom.Centroid().GetX()
                    related_y = related_geom.GetY() if related_geom.GetGeometryType() == ogr.wkbPoint else related_geom.Centroid().GetY()
                    
                    # Berekenen van afstand (vereenvoudigd - in werkelijkheid zou je GIS functies gebruiken)
                    distance = ((boei_x - related_x)**2 + (boei_y - related_y)**2)**0.5
                    
                    # Als objecten dicht bij elkaar liggen, beschouw ze als gerelateerd
                    # De drempelwaarde moet mogelijk aangepast worden afhankelijk van de data
                    if distance < 0.0001:  # ~10m op zeeniveau
                        related_objects.append(related_feature)
                
                # Ga naar de volgende feature
                related_feature = layer.GetNextFeature()
        
        return related_objects
    
    def determine_buoy_system(self, feature):
        """
        Bepaalt of de boei binnengaats of buitengaats betonning is
        
        Args:
            feature (ogr.Feature): OGR feature
            
        Returns:
            str: 'Binnengaats', 'Buitengaats' of 'Onbekend'
        """
        system = ''
        if feature.IsFieldSet('MARSYS'):
            system = feature.GetField('MARSYS')
        
        if not system:
            return 'Onbekend'
            
        try:
            system = int(system)
            
            # IENC/CEVNI systeem duidt op binnenvaart
            if system in [10, 11]:
                return 'Binnengaats'
            else:
                return 'Buitengaats'
        except ValueError:
            return 'Onbekend'
    
    def check_missing_fields(self, buoy_info):
        """
        Controleert op ontbrekende velden en logt waarschuwingen
        
        Args:
            buoy_info (dict): Boei-informatie
        """
        required_fields = ['id', 'type', 'lon', 'lat']
        warning_fields = ['name', 'color', 'shape', 'betonning_type']
        
        for field in required_fields:
            if not buoy_info.get(field):
                logger.error(f"Boei mist verplicht veld: {field}")
                
        for field in warning_fields:
            if not buoy_info.get(field):
                logger.warning(f"Boei {buoy_info.get('id', 'UNKNOWN')} mist veld: {field}")
    
    def save_to_text(self, output_file):
        """
        Slaat de verzamelde boeigegevens op als tekstbestand en drukt ze af naar stdout
        
        Args:
            output_file (str): Uitvoerbestandsnaam
        """
        if not self.buoy_data:
            logger.warning("Geen boeigegevens om op te slaan")
            return
        
        # Definieer de veldnamen en volgorde voor de uitvoer
        field_order = [
            'id', 'name', 'type', 'lon', 'lat', 
            'color', 'shape', 'betonning_type',
            'lateral_mark', 'category', 'system',
            'topmark_shape', 'topmark_color',
            'light_character', 'light_color', 'light_period', 'light_group', 'light_range'
        ]
        
        # Maak mooie kolomkoppen
        field_names = {
            'id': 'ID', 
            'name': 'Naam', 
            'type': 'Type', 
            'lon': 'Longitude', 
            'lat': 'Latitude',
            'color': 'Kleur', 
            'shape': 'Vorm', 
            'betonning_type': 'Betonningstype',
            'lateral_mark': 'Laterale markering', 
            'category': 'Categorie', 
            'system': 'Systeem',
            'topmark_shape': 'Topmark vorm', 
            'topmark_color': 'Topmark kleur',
            'light_character': 'Lichtkarakteristiek', 
            'light_color': 'Lichtkleur', 
            'light_period': 'Lichtperiode',
            'light_group': 'Lichtgroep', 
            'light_range': 'Lichtbereik'
        }
        
        # Bereid de uitvoermap voor
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Maak de uitvoertekst
        header = "# Boei informatie geëxtraheerd uit " + self.enc_file
        header += "\n# Gegenereerd op " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header += "\n# Aantal boeien: " + str(len(self.buoy_data))
        header += "\n\n"
        
        # Voeg kolomkoppen toe
        header += "\t".join([field_names.get(field, field) for field in field_order])
        
        # Bereid de datarijen voor
        rows = []
        for buoy in self.buoy_data:
            row = []
            for field in field_order:
                # Haal de waarde op, gebruik lege string als het veld niet bestaat
                value = buoy.get(field, "")
                # Converteer naar string
                row.append(str(value))
            rows.append("\t".join(row))
        
        # Combineer alles
        output_text = header + "\n" + "\n".join(rows)
        
        # Schrijf naar bestand
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_text)
        
        logger.info(f"{len(self.buoy_data)} boeien opgeslagen in {output_file}")
        
        # Print naar stdout
        print(output_text)


def main():
    """Hoofdfunctie voor het uitvoeren van de extractie"""
    # Gebruik specifieke paden zoals aangegeven
    enc_file = "/home/jeroen/gis_data/ENC/1R7HV002/1R7HV002.000"
    output_dir = "/home/jeroen/gis_data/output/"
    output_file = os.path.join(output_dir, "boeien_data.txt")
    
    # Controleer of het invoerbestand bestaat
    if not os.path.exists(enc_file):
        print(f"Fout: ENC-bestand niet gevonden: {enc_file}")
        sys.exit(1)
    
    # Maak een extractor met het specifieke ENC-bestand
    extractor = BuoyExtractor(enc_file, output_dir)
    
    logger.info("Start extractie van boeigegevens")
    extractor.extract_buoys()
    
    # Sla gegevens op in tekstformaat en druk af naar stdout
    extractor.save_to_text(output_file)
    
    logger.info("Extractie voltooid")


if __name__ == "__main__":
    main()
