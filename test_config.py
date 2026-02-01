from config_loader import load_config

print("Loading config...")
c = load_config('strategy_config.json')
c.print_config()
print("✓ Config loaded successfully!")
