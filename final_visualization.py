import pandas as pd
import matplotlib.pyplot as plt

# Load the CSV file
def plot_grouped_bar_chart(csv_file):
    # Read CSV
    df = pd.read_csv(csv_file)
    
    # Aggregate data: compute mean and standard deviation
    grouped = df.groupby(["scenario", "agent"]).agg({"score": ['mean', 'std']}).reset_index()
    grouped.columns = ["scenario", "agent", "mean_score", "std_score"]
    
    # Pivot table to format for plotting
    pivot = grouped.pivot(index="scenario", columns="agent", values="mean_score")
    std_pivot = grouped.pivot(index="scenario", columns="agent", values="std_score")
    
    # Plot
    ax = pivot.plot(kind='bar', yerr=std_pivot, capsize=4, figsize=(10, 6))
    plt.xlabel("Scenario")
    plt.ylabel("Mean Score with SD")
    plt.title("Mean Score per Scenario and Agent")
    plt.legend(title="Agent")
    plt.xticks(rotation=45)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    # Show plot
    #plt.show()
    plt.savefig('final_results.jpg')

# Example usage
plot_grouped_bar_chart("final_results.csv")