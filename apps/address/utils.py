from .forms import US_STATES

#Currently we only support Puerto Rico as US territory
def is_domestic_delivery(country_code):
    US_TERRITORIES = ['US', 'PR']
    return country_code in US_TERRITORIES

def get_us_state_code(state_name):
    for code, name in US_STATES:
        if name == state_name:
            return code
    return ''
