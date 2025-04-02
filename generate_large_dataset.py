import random
import pandas as pd
import uuid

def generate_small_dataset(num_records=20):  # Changed to 20 records
    categories = [f'Category {i}' for i in range(1, 21)]  # 20 categories
    data = []

    for _ in range(num_records):
        record = {
            'id': str(uuid.uuid4()),
            'category': random.choice(categories),
            'value': random.randint(1, 1000),  # Random values between 1 and 1000
            'time': f'2023-04-{random.randint(1, 30):02d}',  # Random dates in April 2023
            'x_value': random.uniform(0, 100),  # Random float for X-axis
            'y_value': random.uniform(0, 100)   # Random float for Y-axis
        }
        data.append(record)

    return pd.DataFrame(data)

# Generate the dataset
small_dataset = generate_small_dataset()  # Now generates 20 records

# Save to a CSV file
small_dataset.to_csv('small_dataset.csv', index=False)

print("Small dataset generated and saved to 'small_dataset.csv'")