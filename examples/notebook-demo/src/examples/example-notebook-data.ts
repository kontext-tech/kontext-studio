import type { NotebookDocument } from "@kontext-labs/notebook";

export const EXAMPLE_NOTEBOOK: NotebookDocument = {
   title: "Data Analysis Report",
   created: 1753610987078,
   modified: 1754100217120,
   blocks: [
      {
         id: "39b057f2-f172-4a4c-ad7c-3470f731ca43",
         type: "image",
         data: {
            caption: "Logo",
            withBorder: false,
            withBackground: false,
            stretched: false,
            file: {
               url: "https://kontext.tech/resources/logo.png"
            }
         }
      },
      {
         id: "234b5649-20a3-456f-999c-16230de3b617",
         type: "header",
         data: {
            text: "Executive Summary",
            level: 2
         }
      },
      {
         id: "b72fc3bf-ee42-49f3-8bfa-651cd662ec50",
         type: "paragraph",
         data: {
            text: "This report presents our <b>Q4 2024</b> sales performance analysis with key insights and recommendations."
         }
      },
      {
         id: "e697e176-6f27-4efb-a6c3-110885d970aa",
         type: "header",
         data: {
            text: "Key Findings",
            level: 2
         }
      },
      {
         id: "ead88dd9-cd26-48d2-8bc8-915ee243c22d",
         type: "list",
         data: {
            style: "unordered",
            meta: {},
            items: [
               {
                  content: "Sales increased by 25% compared to Q3",
                  meta: {},
                  items: []
               },
               {
                  content: "Customer acquisition cost decreased by <i>15%</i>",
                  meta: {},
                  items: []
               },
               {
                  content: "Revenue per customer grew by 12%",
                  meta: {},
                  items: []
               }
            ]
         }
      },
      {
         id: "a8f4d7e2-3c1b-4a5e-9f8d-2e7c4b9a1f6e",
         type: "chart",
         data: {
            config: {
               chartType: "column",
               height: 400,
               colorPalette: "kontext",
               title: "Revenue by Region",
               xField: "month",
               yField: "revenue",
               colorField: "region",
               stack: true,
               aggregate: "sum"
            },
            dataRef: {
               dataId: "57883424-55e1-4763-9b64-b0b7f0daef5e"
            }
         }
      },
      {
         id: "a8f4d7e2-3c1b-4a5e-9f8d-2e7c4b9a1f6e-pca",
         type: "code",
         data: {
            code: 'import matplotlib.pyplot as plt\nfrom sklearn import datasets\nfrom sklearn.decomposition import PCA\nimport numpy as np\n\n# Load Iris dataset\niris = datasets.load_iris()\n\nfig = plt.figure(1, figsize=(8, 6))\nax = fig.add_subplot(111, projection="3d", elev=-150, azim=110)\n\nX_reduced = PCA(n_components=3).fit_transform(iris.data)\nscatter = ax.scatter(\n    X_reduced[:, 0],\n    X_reduced[:, 1],\n    X_reduced[:, 2],\n    c=iris.target,\n    s=40,\n)\n\nax.set(\n    title="First three principal components (Iris Dataset)",\n    xlabel="1st Principal Component",\n    ylabel="2nd Principal Component",\n    zlabel="3rd Principal Component",\n)\nax.xaxis.set_ticklabels([])\nax.yaxis.set_ticklabels([])\nax.zaxis.set_ticklabels([])\n\n# Add a legend\nlegend1 = ax.legend(\n    scatter.legend_elements()[0],\n    iris.target_names.tolist(),\n    loc="upper right",\n    title="Classes",\n)\nax.add_artist(legend1)\n\nplt.show()\n\nprint("PCA analysis complete.")',
            language: "python",
            runtimePreference: "client",
            showCode: true,
            outputs: []
         }
      },
      {
         id: "c8e1d2f3-a4b5-6c7d-8e9f-0a1b2c3d4e5f",
         type: "header",
         data: {
            text: "Aggregated Insights",
            level: 2
         }
      },
      {
         id: "d9e0f1a2-b3c4-5d6e-7f8a-9b0c1d2e3f4a",
         type: "paragraph",
         data: {
            text: "The following charts demonstrate built-in data aggregation, allowing us to see regional contribution and average performance across all months."
         }
      },
      {
         id: "e0f1a2b3-c4d5-6e7f-8a9b-0c1d2e3f4a5b",
         type: "chart",
         data: {
            config: {
               chartType: "pie",
               height: 400,
               title: "Total Revenue Share by Region",
               angleField: "revenue",
               colorField: "region",
               aggregate: "sum"
            },
            dataRef: {
               dataId: "57883424-55e1-4763-9b64-b0b7f0daef5e"
            }
         }
      },
      {
         id: "f1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c",
         type: "chart",
         data: {
            config: {
               chartType: "column",
               height: 300,
               title: "Monthly Revenue Trend (Global)",
               xField: "month",
               yField: "revenue",
               aggregate: "sum"
            },
            dataRef: {
               dataId: "57883424-55e1-4763-9b64-b0b7f0daef5e"
            }
         }
      },
      {
         id: "b9e8f3c4-2d1a-4b6e-8c5d-9f7e2a3b1c8d",
         type: "chart",
         data: {
            config: {
               chartType: "dualAxes",
               height: 400,
               colorPalette: "greens",
               title: "Monthly Performance: Revenue vs Customer Count",
               xField: "month",
               leftYField: "revenue",
               leftChartType: "interval",
               leftAggregate: "sum",
               leftColorField: "region",
               leftStack: true,
               rightYField: "customer_count",
               rightChartType: "line",
               rightAggregate: "sum",
               rightColorField: "region"
            },
            dataRef: {
               dataId: "57883424-55e1-4763-9b64-b0b7f0daef5e"
            }
         }
      },
      {
         id: "c2a8c47c-7d48-4db0-9e3f-9c5e9aef2001",
         type: "header",
         data: {
            text: "Advanced Chart Gallery",
            level: 2
         }
      },
      {
         id: "c2a8c47c-7d48-4db0-9e3f-9c5e9aef2002",
         type: "paragraph",
         data: {
            text: "This section showcases the newly supported histogram, box, radar, and stock charts. Histogram and box reuse the sales dataset, while radar and stock each introduce a dedicated source block so the chart fields line up with the data naturally."
         }
      },
      {
         id: "c2a8c47c-7d48-4db0-9e3f-9c5e9aef2003",
         type: "chart",
         data: {
            config: {
               chartType: "histogram",
               height: 320,
               title: "Revenue Distribution by Region",
               binField: "revenue",
               colorField: "region",
               binNumber: 6
            },
            dataRef: {
               dataId: "57883424-55e1-4763-9b64-b0b7f0daef5e"
            }
         }
      },
      {
         id: "c2a8c47c-7d48-4db0-9e3f-9c5e9aef2004",
         type: "chart",
         data: {
            config: {
               chartType: "box",
               height: 320,
               title: "Average Order Value Spread by Region",
               xField: "region",
               yField: "avg_order_value",
               colorField: "region",
               boxType: "boxplot"
            },
            dataRef: {
               dataId: "57883424-55e1-4763-9b64-b0b7f0daef5e"
            }
         }
      },
      {
         id: "c2a8c47c-7d48-4db0-9e3f-9c5e9aef2010",
         type: "sql",
         data: {
            title: "Capability Benchmark Source",
            code: "-- Benchmark scores across shared product dimensions\nSELECT\n    capability,\n    product_area,\n    score\nFROM platform_capability_benchmark\nORDER BY capability, product_area;",
            dataRef: {
               dataId: "67883424-55e1-4763-9b64-b0b7f0daef5e"
            }
         }
      },
      {
         id: "c2a8c47c-7d48-4db0-9e3f-9c5e9aef2005",
         type: "chart",
         data: {
            config: {
               chartType: "radar",
               height: 360,
               title: "Capability Benchmark by Product Area",
               xField: "capability",
               yField: "score",
               colorField: "product_area",
               coordinateType: "polar",
               point: {
                  size: 3
               },
               area: {
                  style: {
                     fillOpacity: 0.12
                  }
               },
               axis: {
                  x: {
                     grid: true,
                     line: true
                  },
                  y: {
                     nice: true,
                     tickCount: 5
                  }
               },
               scale: {
                  score: {
                     domain: [0, 100]
                  }
               }
            },
            dataRef: {
               dataId: "67883424-55e1-4763-9b64-b0b7f0daef5e"
            }
         }
      },
      {
         id: "c2a8c47c-7d48-4db0-9e3f-9c5e9aef2011",
         type: "sql",
         data: {
            title: "KONT OHLC Source",
            code: "-- Demo OHLC series for the KONT ticker\nSELECT\n    trade_date,\n    ticker,\n    open_price,\n    close_price,\n    low_price,\n    high_price,\n    volume\nFROM market_trading_snapshot\nWHERE ticker = 'KONT'\nORDER BY trade_date;",
            dataRef: {
               dataId: "77883424-55e1-4763-9b64-b0b7f0daef5e"
            }
         }
      },
      {
         id: "c2a8c47c-7d48-4db0-9e3f-9c5e9aef2006",
         type: "chart",
         data: {
            config: {
               chartType: "stock",
               height: 360,
               title: "KONT Daily Price Range",
               xField: "trade_date",
               yField: ["open_price", "close_price", "low_price", "high_price"]
            },
            dataRef: {
               dataId: "77883424-55e1-4763-9b64-b0b7f0daef5e"
            }
         }
      },
      {
         id: "153016da-9080-4217-8c6c-56118ff83769",
         type: "header",
         data: {
            text: "SQL Analysis",
            level: 2
         }
      },
      {
         id: "10235713-5bd7-4ff1-adef-68b3068af560",
         type: "sql",
         data: {
            title: "Sales Performance Data",
            code: "-- Query to analyze monthly sales performance\nSELECT\n    month,\n    region,\n    revenue,\n    units_sold,\n    customer_count,\n    avg_order_value\nFROM sales_performance\nWHERE year = 2024\nORDER BY month, region;",
            dataRef: { dataId: "57883424-55e1-4763-9b64-b0b7f0daef5e" }
         }
      },
      {
         id: "4a635024-30f9-4334-83a9-6344838bcf35",
         type: "header",
         data: {
            text: "Python Data Science",
            level: 2
         }
      },
      {
         id: "9c3e2a1b-4d5e-6f7g-8h9i-0j1k2l3m4n5o",
         type: "code",
         data: {
            code: "import numpy as np\nimport matplotlib.pyplot as plt\n\n# Generate some data\nx = np.linspace(0, 10, 100)\ny = np.sin(x)\n\n# Create a plot\nplt.figure(figsize=(8, 4))\nplt.plot(x, y, label='Sine Wave')\nplt.title('Sample Plot')\nplt.grid(True)\nplt.legend()\nplt.show()\n\nprint(f\"Generated {len(x)} points.\")",
            language: "python",
            runtimePreference: "client",
            showCode: true,
            outputs: []
         }
      },
      {
         id: "8d9e0f1a-b2c3-4d5e-6f7g-8h9i0j1k2l3m",
         type: "code",
         data: {
            code: 'def greet(name: str) -> None:\n    print(f"Hello, {name}!")\n\n\ngreet("Kontext User")',
            language: "python",
            showCode: true
         }
      },
      {
         id: "f47ac10b-58cc-4372-a567-0e02b2c3d479",
         type: "header",
         data: {
            text: "Data Visualization",
            level: 2
         }
      },
      {
         id: "7f9e2a3b-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
         type: "mermaid",
         data: {
            code: "graph TD\n    A[Sales Data] --> B{Analysis}\n    B --> C[Revenue Growth]\n    B --> D[Customer Metrics]\n    B --> E[Regional Performance]\n    C --> F[Q4 Results]\n    D --> F\n    E --> F\n    F --> G[Strategic Recommendations]"
         }
      },
      {
         id: "91a013e5-f2e0-47de-b9dc-f9a2c2303a84",
         type: "header",
         data: {
            text: "Recommendations",
            level: 2
         }
      },
      {
         id: "fcf6ebb1-8f8d-4f56-9d9a-192dc9feec30",
         type: "list",
         data: {
            style: "ordered",
            meta: {
               counterType: "numeric"
            },
            items: [
               {
                  content:
                     "<b>Increase Marketing Spend</b>: Based on improved CAC metrics",
                  meta: {},
                  items: []
               },
               {
                  content:
                     "<b>Expand Customer Success</b>: Focus on revenue per customer growth",
                  meta: {},
                  items: []
               },
               {
                  content:
                     "<b>Scale Operations</b>: Prepare for continued growth trajectory",
                  meta: {},
                  items: []
               }
            ]
         }
      },
      {
         id: "45ecfa1b-0577-47e6-b68b-90526396d2f4",
         type: "header",
         data: {
            text: "Conclusion",
            level: 2
         }
      },
      {
         id: "b2c04a05-55a7-42a3-a086-4abe6c61b63a",
         type: "paragraph",
         data: {
            text: "The data shows strong performance across all key metrics, indicating successful execution of our growth strategy."
         }
      },
      {
         id: "d07e554d-d843-4525-b805-dc32d831d692",
         type: "header",
         data: {
            text: "References",
            level: 2
         }
      },
      {
         id: "91fa5c00-dc66-440b-8730-729d54ac79a5",
         type: "list",
         data: {
            style: "unordered",
            meta: {},
            items: [
               {
                  content:
                     '<a href="https://example.com/q4-sales-data" target="_blank">Q4 Sales Data</a>',
                  meta: {},
                  items: []
               },
               {
                  content:
                     '<a href="https://kontext.tech/" target="_blank">Kontext</a>',
                  meta: {},
                  items: []
               }
            ]
         }
      }
   ],
   metadata: {
      description: "Comprehensive analysis of Q4 sales data",
      keyWords: "data analysis, sales, Q4, visualization",
      languageCode: "en",
      tags: ["analytics", "sales", "quarterly-report"],
      imageUrl: "https://kontext.tech/resources/logo.png",
      isPublished: true
   }
};
