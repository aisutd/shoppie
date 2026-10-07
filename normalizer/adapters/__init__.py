from normalizer.adapters.bestbuy import BestBuyAdapter
from normalizer.adapters.target import TargetAdapter
from normalizer.adapters.walmart import WalmartAdapter


ADAPTERS = {
    "target": TargetAdapter(),
    "walmart": WalmartAdapter(),
    "bestbuy": BestBuyAdapter(),
}