import re
from flask import Flask, jsonify
import requests
from typing import List
from threading import Timer
from datetime import datetime, timedelta
from requests.exceptions import RequestException
import logging
import time

class AuctionItem:
    def __init__(self, uuid, item_name, item_lore, category, tier, claimed, bin_status, starting_bid):
        self.uuid = uuid
        self.item_name = item_name
        self.item_lore = item_lore
        self.category = category
        self.tier = tier
        self.claimed = claimed
        self.bin_status = bin_status
        self.starting_bid = starting_bid

logging.basicConfig(filename='error.log', level=logging.ERROR)

class AuctionService:
    def get_auction_items(self) -> List[AuctionItem]:
        auction_items = []
        page = 0
        more_pages = True
        retry_attempts = 5 

        while more_pages:
            try:
                response = requests.get(f'https://api.hypixel.net/skyblock/auctions?page={page}', timeout=10)
                response.raise_for_status() 
                data = response.json()
                total_pages = data['totalPages']
                print(f"Processando página {page + 1} de {total_pages}...")

                more_pages = page + 1 < total_pages
                page += 1

                for item in data['auctions']:
                    auction_items.append(AuctionItem(
                        uuid=item['uuid'],
                        item_name=item['item_name'],
                        item_lore=item.get('item_lore', ''),
                        category=item['category'],
                        tier=item['tier'],
                        claimed=item['claimed'],
                        bin_status=item['bin'],
                        starting_bid=item['starting_bid']
                    ))

            except RequestException as e:
                logging.error(f"Erro ao fazer requisição: {e}")
                retry_attempts -= 1
                if retry_attempts > 0:
                    print(f"Tentando novamente... ({retry_attempts} tentativas restantes)")
                    time.sleep(5)  
                else:
                    print("Falha ao obter dados do servidor após várias tentativas.")
                    break  

        return auction_items

class ArmorFilterService:
    valid_armor_attributes = [
        "Arachno Resistance", "Blazing Resistance", "Breeze", "Dominance", 
        "Ender Resistance", "Experience", "Fortitude", "Life Regeneration", 
        "Lifeline", "Magic Find", "Mana Pool", "Mana Regeneration", 
        "Vitality", "Speed", "Undead Resistance", "Veteran"
    ]

    valid_armor_names = ["Crimson", "Aurora", "Terror", "Hollow", "Fervor"]
    valid_armor_pieces = ["Helmet", "Chestplate", "Leggings", "Boots"]
    
    valid_equipments = ["Molten Belt", "Molten Bracelet", "Molten Cloak", "Molten Necklace"]
    
    shard = ["Attribute Shard"]

    def __init__(self, auction_service: AuctionService):
        self.auction_service = auction_service
        self.last_fetched = datetime.min
        self.cached_items = []

    def refresh_data(self):
        print("Refreshing auction data...")
        self.cached_items = self.auction_service.get_auction_items()
        self.last_fetched = datetime.now()

    def filter_items(self) -> List[AuctionItem]:
        if datetime.now() - self.last_fetched > timedelta(minutes=5):
            self.refresh_data()

        # Filtra armaduras, equipamentos e shards com bin_status True
        armors = [item for item in self.cached_items 
                if item.item_name and self.matches_armor_name(item.item_name) 
                and self.matches_armor_piece(item.item_name)
                and item.bin_status == True]

        equipments = [item for item in self.cached_items 
                    if item.item_name and self.matches_equipment_name(item.item_name)
                    and item.bin_status == True]

        shards = [item for item in self.cached_items
                if item.item_name and "Attribute Shard" in item.item_name
                and item.bin_status == True]

        # Combina os três resultados
        return armors + equipments + shards


    def matches_armor_name(self, item_name: str) -> bool:
        return any(name.lower() in item_name.lower() for name in self.valid_armor_names)
    
    def matches_armor_piece(self, item_name: str) -> bool:
        return any(piece.lower() in item_name.lower() for piece in self.valid_armor_pieces)

    def matches_equipment_name(self, item_name: str) -> bool:
        return any(equipment.lower() in item_name.lower() for equipment in self.valid_equipments)

    def extract_attributes_from_lore(self, item_lore):
        attributelist = self.valid_armor_attributes

        attribute_regex = re.compile(
            f"({'|'.join(attributelist)}) ([IVXLCDM]+)"
        )
        
        shard_regex = re.compile(r"Attribute Shard")

        normalized_lore = re.sub(r'§[0-9a-fk-or]', '', item_lore)
        
        attributes = []
        for line in normalized_lore.split('\n'):
            # Verifica atributos regulares
            match = attribute_regex.search(line)
            if match:
                attribute_name = match.group(1)
                attribute_level = match.group(2)
                attributes.append({'name': attribute_name, 'level': attribute_level})

            # Verifica Attribute Shard
            shard_match = shard_regex.search(line)
            if shard_match:
                attributes.append({'name': 'Attribute Shard', 'level': 'N/A'})
        
        return attributes




auction_service = AuctionService()
armor_filter_service = ArmorFilterService(auction_service)

def refresh_data_periodically():
    armor_filter_service.refresh_data()
    Timer(300, refresh_data_periodically).start()  # Refresh every 300 seconds (5 minutes)

refresh_data_periodically()

app = Flask(__name__)

@app.route('/filtered_items', methods=['GET'])
def get_filtered_items():
    filtered_items = armor_filter_service.filter_items()
    response = [
        {
            "uuid": item.uuid,
            "name": item.item_name,
            "starting_bid": item.starting_bid,
            "tier": item.tier,
            "bin_status": item.bin_status,
            "attributes": armor_filter_service.extract_attributes_from_lore(item.item_lore) 
        } for item in filtered_items
    ]
    return jsonify(response)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


