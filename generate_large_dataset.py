import random
import pandas as pd

def generate_small_dataset(num_records=20):
    categories = [f'Category {i}' for i in range(1, 21)]  # 20 categories
    data = []

    for i in range(1, num_records + 1):
        record = {
            'ID': i,  # Sequential ID
            'Date': f'2023-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}',  # Random dates in 2023
            'Category': random.choice(categories),
            'Sales': random.randint(1000, 20000),  # Random sales figures
            'Profit': random.randint(100, 5000),    # Random profit figures
            'Units Sold': random.randint(1, 500),   # Random units sold
            'Customer Satisfaction': random.uniform(1, 10),  # Random satisfaction score
            'Marketing Spend': random.randint(100, 3000)  # Random marketing spend
        }
        data.append(record)

    return pd.DataFrame(data)

# Generate the dataset
small_dataset = generate_small_dataset()  # Generates 20 records

# Save to a CSV file
small_dataset.to_csv('small_dataset.csv', index=False)

print("Small dataset generated and saved to 'small_dataset.csv'")