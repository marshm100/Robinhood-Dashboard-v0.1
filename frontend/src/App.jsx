import { useState, useEffect, useCallback } from 'react';
import './App.css';
import { 
  Chart as ChartJS, 
  CategoryScale, 
  LinearScale, 
  PointElement,
  LineElement,
  BarElement, 
  ScatterController,
  Title, 
  Tooltip, 
  Legend,
  TimeScale,
  Filler,
  ArcElement // Import ArcElement for Pie/Doughnut charts
} from 'chart.js';
import { Bar, Scatter, Line, Pie } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';
import { parse } from 'date-fns';

// Register Chart.js components
ChartJS.register(
  CategoryScale, 
  LinearScale, 
  PointElement,
  LineElement,
  BarElement, 
  ScatterController,
  Title, 
  Tooltip, 
  Legend,
  TimeScale,
  Filler,
  ArcElement // Register ArcElement
);

// --- Cyberpunk Chart Options (shared base) ---
const cyberpunkChartOptions = {
  responsive: true,
  maintainAspectRatio: false, // Allow height control via container
  plugins: {
    legend: {
      position: 'top',
      labels: {
        color: '#00ffcc', // Neon teal/cyan for legend text
        font: {
          family: "'Courier New', Courier, monospace", // Monospace font
        },
      },
    },
    title: {
      display: true,
      text: 'Chart Title', // Default title, override in specific charts
      color: '#ff00ff', // Neon pink/magenta for title
      font: {
        size: 18,
        family: "'Courier New', Courier, monospace",
      },
    },
    tooltip: {
      backgroundColor: 'rgba(0, 0, 0, 0.8)', // Dark tooltip background
      titleColor: '#ff00ff', // Neon pink for tooltip title
      bodyColor: '#00ffcc', // Neon teal for tooltip body
      borderColor: '#ff00ff', // Neon pink border
      borderWidth: 1,
      titleFont: {
        family: "'Courier New', Courier, monospace",
      },
      bodyFont: {
        family: "'Courier New', Courier, monospace",
      },
      callbacks: { // Default tooltip callback
         label: function(context) {
             let label = context.dataset.label || '';
             if (label) {
                 label += ': ';
             }
             if (context.parsed.y !== null) {
                 // Default formatting, specific charts might override
                 label += context.parsed.y.toFixed(2);
             }
             return label;
         }
      }
    },
  },
  scales: {
    x: { // Default x-axis config (can be overridden)
      ticks: {
        color: '#00ffcc', // Neon teal for x-axis labels
        font: {
          family: "'Courier New', Courier, monospace",
        },
      },
      grid: {
        color: 'rgba(0, 255, 204, 0.2)', // Faint neon teal grid lines
        borderColor: '#00ffcc', // Axis line color
      },
    },
    y: { // Default y-axis config
      ticks: {
        color: '#00ffcc', // Neon teal for y-axis labels
        font: {
          family: "'Courier New', Courier, monospace",
        },
        // Default callback, override for specific formatting (like currency/percentage)
        callback: function(value) {
          return value;
        }
      },
      grid: {
        color: 'rgba(0, 255, 204, 0.2)', // Faint neon teal grid lines
        borderColor: '#00ffcc', // Axis line color
      },
       title: { // Default y-axis title
           display: true,
           text: 'Value',
           color: '#00ffcc',
            font: {
               family: "'Courier New', Courier, monospace",
            },
       }
    },
  },
  // Default interaction settings
  interaction: {
    mode: 'index', // Show tooltips for all datasets at the same x-index
    intersect: false, // Tooltip activates when hovering near points, not just directly on them
  },
  hover: {
    mode: 'index',
    intersect: false,
  },
};

// Define a set of cyberpunk colors for the pie chart slices
const cyberpunkPieColors = [
  '#ff00ff', // Neon Pink
  '#00ffcc', // Neon Teal
  '#ffa500', // Neon Orange
  '#00ff00', // Neon Green
  '#ff4500', // Orange-Red
  '#ffff00', // Neon Yellow
  '#00ffff', // Cyan
  '#ff0000', // Bright Red
];

function App() {
  // --- State Variables using useState hook ---
  // These variables hold data that can change and cause the component to re-render.
  
  // Holds the file object selected by the user for upload.
  // Initial value is null (no file selected).
  const [file, setFile] = useState(null);
  
  // Stores messages to show the user about the upload process (e.g., "Success!", "Error: ...").
  // Initial value is null (no status message).
  const [uploadStatus, setUploadStatus] = useState(null);
  
  // Tracks whether a file upload or initial data loading is happening.
  // Used to show loading indicators (like spinners).
  // Initial value is false (not loading).
  const [isLoading, setIsLoading] = useState(false);
  
  // -- State for fetched data --
  // These states hold the data fetched from the backend API endpoints.
  // Each has a corresponding loading state (e.g., isLoadingXYZ) and potentially an error state (e.g., errorXYZ).

  // Stores the list of assets in the portfolio (e.g., [{ ticker: 'AAPL', name: 'Apple Inc.', allocation_percentage: 50 }]).
  const [portfolioComposition, setPortfolioComposition] = useState([]);
  const [loadingComposition, setLoadingComposition] = useState(false); // Tracks loading for composition data.
  
  // Stores data for style analysis (e.g., sector weights, P/E ratio) and portfolio totals.
  const [styleAnalysis, setStyleAnalysis] = useState({ styleAnalysis: [], portfolioTotals: {} });
  const [loadingStyleAnalysis, setLoadingStyleAnalysis] = useState(false); // Tracks loading for style analysis.
  
  // Stores the date associated with the fundamentals data used.
  const [fundamentalsDate, setFundamentalsDate] = useState('');
  const [loadingFundamentalsDate, setLoadingFundamentalsDate] = useState(false); // Tracks loading.
  
  // Stores data comparing portfolio returns to benchmark returns (active return).
  const [activeReturns, setActiveReturns] = useState({ activeReturns: [] });
  const [loadingActiveReturns, setLoadingActiveReturns] = useState(false); // Tracks loading.
  
  // Stores data on how the portfolio performed during market up vs. down periods.
  const [marketPerformance, setMarketPerformance] = useState({ marketPerformance: [] });
  const [loadingMarketPerformance, setLoadingMarketPerformance] = useState(false); // Tracks loading.
  
  // Stores calculated risk and return metrics (Sharpe Ratio, Volatility, etc.).
  const [riskReturnMetrics, setRiskReturnMetrics] = useState(null);
  const [loadingRiskReturn, setLoadingRiskReturn] = useState(false); // Tracks loading.
  
  // Stores data for the annual returns chart.
  const [annualReturnsData, setAnnualReturnsData] = useState(null);
  const [isLoadingAnnualReturns, setIsLoadingAnnualReturns] = useState(true); // Tracks loading.
  const [errorAnnualReturns, setErrorAnnualReturns] = useState(null); // Stores error message if fetching fails.
  
  // Stores data for the monthly returns chart.
  const [monthlyReturnsData, setMonthlyReturnsData] = useState(null);
  const [isLoadingMonthlyReturns, setIsLoadingMonthlyReturns] = useState(true); // Tracks loading.
  const [errorMonthlyReturns, setErrorMonthlyReturns] = useState(null); // Stores error message.
  
  // Stores data for the portfolio growth chart (value over time vs. benchmark).
  const [portfolioGrowthData, setPortfolioGrowthData] = useState(null);
  const [isLoadingPortfolioGrowth, setIsLoadingPortfolioGrowth] = useState(true); // Tracks loading.
  const [errorPortfolioGrowth, setErrorPortfolioGrowth] = useState(null); // Stores error message.
  
  // Stores the ticker symbol of the benchmark selected by the user (e.g., 'SPY').
  const [selectedBenchmark, setSelectedBenchmark] = useState('SPY'); // Default is SPY index.
  
  // Stores data for the drawdown chart (percentage drop from peak value over time).
  const [drawdownData, setDrawdownData] = useState(null);
  const [isLoadingDrawdown, setIsLoadingDrawdown] = useState(true); // Tracks loading.
  const [errorDrawdown, setErrorDrawdown] = useState(null); // Stores error message.

  const handleFileChange = (event) => {
    setFile(event.target.files[0]);
    setUploadStatus(null);
  };

  const handleUpload = async () => {
    if (!file) {
      alert('Please select a file first!');
      return;
    }

    setIsLoading(true);
    setUploadStatus(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('http://localhost:3002/upload', {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || 'Upload failed');
      }

      setUploadStatus({
        type: 'success',
        message: `Success! Uploaded ${result.insertedCount} transactions.`
      });

      // --- Trigger data refetch after successful upload ---
      // Fetch data that depends on transactions being present
      fetchAnnualReturns();
      fetchMonthlyReturns();
      fetchPortfolioGrowth();
      fetchDrawdownData();
      fetchRiskReturnMetrics();
      fetchActiveReturns(); // Call fetchActiveReturns here
      fetchMarketPerformance(); // Call fetchMarketPerformance here
      // Other fetches if they depend on transaction data
      // fetchPortfolioComposition(); // Might depend on config, not just upload
      // fetchStyleAnalysis(); // Might depend on config, not just upload

    } catch (error) {
      console.error('Error uploading file:', error);
      setUploadStatus({
        type: 'error',
        message: `Error: ${error.message}`
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Comment out the unused portfolio configuration functions
  /*
  // Handle changes to allocation inputs
  const handleAllocationChange = (index, field, value) => {
    const newAllocations = [...allocations];
    newAllocations[index][field] = value;
    setAllocations(newAllocations);
  };

  // Add a new allocation input row
  const addAllocation = () => {
    setAllocations([...allocations, { ticker: '', allocation_percentage: '' }]);
  };

  // Remove an allocation input row
  const removeAllocation = (index) => {
    if (allocations.length > 1) {
      const newAllocations = allocations.filter((_, i) => i !== index);
      setAllocations(newAllocations);
    }
  };
  */

  // --- Fetch Functions (wrapped in useCallback) ---

  // Step 30: Define a function to fetch annual returns data from the backend.
  // useCallback memoizes the function so it's not recreated on every render, 
  // unless its dependencies (selectedBenchmark) change.
  const fetchAnnualReturns = useCallback(async () => {
    // Step 31: Set loading state to true before fetching.
    setIsLoadingAnnualReturns(true);
    // Step 32: Clear any previous errors.
    setErrorAnnualReturns(null);
    try {
      // Step 33: Fetch data from the backend API, including the selected benchmark.
      const response = await fetch(`http://localhost:3002/annual-returns?benchmark=${selectedBenchmark}`);
      // Step 34: Check if the fetch was successful.
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      // Step 35: Parse the JSON response data.
      const data = await response.json();
      // Step 36: Update the state with the fetched data.
      setAnnualReturnsData(data);
    } catch (error) {
      // Step 37: Handle any errors during fetching.
      console.error("Error fetching annual returns:", error);
      // Step 38: Set the error state.
      setErrorAnnualReturns(error.message);
      // Step 39: Clear the data state on error.
      setAnnualReturnsData(null);
    } finally {
      // Step 40: Set loading state to false after fetch completes (success or error).
      setIsLoadingAnnualReturns(false);
    }
  }, [selectedBenchmark]); // Dependency array: function re-runs if selectedBenchmark changes.

  // Step 41: Define a function to fetch monthly returns data (similar logic to annual returns).
  const fetchMonthlyReturns = useCallback(async () => {
    // Step 42: Set loading state and clear errors.
    setIsLoadingMonthlyReturns(true);
    setErrorMonthlyReturns(null);
    try {
      // Step 43: Fetch data from the backend, including the benchmark.
      const response = await fetch(`http://localhost:3002/monthly-returns?benchmark=${selectedBenchmark}`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      // Step 44: Update state with fetched data.
      setMonthlyReturnsData(data);
    } catch (error) {
      // Step 45: Handle fetch errors.
      console.error("Error fetching monthly returns:", error);
      setErrorMonthlyReturns(error.message);
      setMonthlyReturnsData(null);
    } finally {
      // Step 46: Set loading state to false.
      setIsLoadingMonthlyReturns(false);
    }
  }, [selectedBenchmark]); // Dependency: selectedBenchmark.

  // Step 47: Define a function to fetch portfolio growth data.
  const fetchPortfolioGrowth = useCallback(async () => {
    // Step 48: Set loading state and clear errors.
    setIsLoadingPortfolioGrowth(true);
    setErrorPortfolioGrowth(null);
    console.log(`Fetching portfolio growth data with benchmark: ${selectedBenchmark}`);
    try {
      // Step 49: Fetch data from the backend, including the benchmark.
      const response = await fetch(`http://localhost:3002/portfolio-growth?benchmark=${selectedBenchmark}`);
      // Step 50: Handle non-OK responses (e.g., 404 if no transactions uploaded).
      if (!response.ok) {
        const errorData = await response.json(); // Try to get error message from backend
        console.error(`Error fetching portfolio growth data: ${response.status}`, errorData);
        // Step 51: Set a user-friendly error message.
        setErrorPortfolioGrowth(errorData.message || 'Failed to fetch portfolio data. Please upload transactions first.');
        setPortfolioGrowthData(null); // Clear data state.
        return; // Stop execution.
      }
      
      // Step 52: Parse the successful JSON response.
      const data = await response.json();
      console.log("Fetched Portfolio Growth Data:", data);
      
      // Step 53: Validate the fetched data structure.
      if (!Array.isArray(data) || data.length === 0) {
        console.warn("Fetched portfolio growth data is empty or not an array");
        setErrorPortfolioGrowth('No portfolio data available. Please upload transactions first.');
        setPortfolioGrowthData(null);
        return;
      }
      
      // Step 54: Check if data format needs transformation (optional, based on backend consistency).
      // This block tries to handle cases where the backend might return data in a slightly different shape.
      if (data[0] && (!Object.hasOwn(data[0], 'portfolioValue') || !Object.hasOwn(data[0], 'benchmarkValue'))) {
        console.warn("Fetched portfolio growth data is not in the expected {date, portfolioValue, benchmarkValue} format. Attempting transformation.");
        // Step 55: Transform the data into the expected format.
        const transformedData = data.map(item => ({
          date: item.date || new Date().toISOString().split('T')[0], // Fallback date
          portfolioValue: item.portfolioValue || item.value || 0, // Try different possible value keys
          benchmarkValue: item.benchmarkValue || 0 // Fallback benchmark value
        }));
        setPortfolioGrowthData(transformedData); // Update state with transformed data.
      } else {
        // Step 56: If data is already in the correct format, update state directly.
        setPortfolioGrowthData(data);
      }
    } catch (error) {
      // Step 57: Handle any unexpected errors during fetch or processing.
      console.error("Error fetching portfolio growth:", error);
      setErrorPortfolioGrowth(error.message);
      setPortfolioGrowthData(null);
    } finally {
      // Step 58: Set loading state to false.
      setIsLoadingPortfolioGrowth(false);
    }
  }, [selectedBenchmark]); // Dependency: selectedBenchmark.

  // Step 59: Define a function to fetch risk and return metrics.
  const fetchRiskReturnMetrics = useCallback(async () => {
    // Step 60: Set loading state.
    setLoadingRiskReturn(true);
    try {
      // Step 61: Fetch data from the backend, including the benchmark.
      const response = await fetch(`http://localhost:3002/risk-return?benchmark=${selectedBenchmark}`);
      
      // Step 62: Handle non-OK responses.
      if (!response.ok) {
        const errorData = await response.json();
        console.error(`Error fetching risk-return metrics: ${response.status}`, errorData);
        setRiskReturnMetrics(null);
        // Optionally set an error state here if one exists for risk/return.
        return;
      }
      
      // Step 63: Parse the successful JSON response.
      const data = await response.json();

      // Step 64: Check the structure of the response and update state.
      if (data && data.metrics) {
        setRiskReturnMetrics(data.metrics); // Update state with the metrics object.
      } else if (data && data.error) {
        // Handle cases where the backend explicitly returned an error message.
        console.error('Error from risk-return endpoint:', data.error);
        setRiskReturnMetrics(null);
      } else {
        // Handle unexpected response formats.
        console.error('Unexpected response format from risk-return endpoint');
        setRiskReturnMetrics(null);
      }
    } catch (error) {
      // Step 65: Handle fetch or processing errors.
      console.error('Failed to fetch risk and return metrics:', error);
      setRiskReturnMetrics(null);
    } finally {
      // Step 66: Set loading state to false.
      setLoadingRiskReturn(false);
    }
  }, [selectedBenchmark]); // Dependency: selectedBenchmark.

  // Step 67: Define a function to fetch portfolio drawdown data.
  const fetchDrawdownData = useCallback(async () => {
    // Step 68: Set loading state and clear errors.
    setIsLoadingDrawdown(true);
    setErrorDrawdown(null);
    console.log("Fetching portfolio drawdown data...");
    try {
      // Step 69: Fetch data from the backend endpoint.
      const response = await fetch(`http://localhost:3002/portfolio-drawdown`);
      // Step 70: Handle non-OK responses.
      if (!response.ok) {
        const errorData = await response.json();
        console.error(`Error fetching portfolio drawdown data: ${response.status}`, errorData);
        // Step 71: Set user-friendly error message.
        setErrorDrawdown(errorData.message || 'Failed to fetch drawdown data. Please upload transactions first.');
        setDrawdownData(null); // Clear data state.
        return;
      }
      // Step 72: Parse the successful JSON response.
      const data = await response.json();
      console.log("Fetched Drawdown Data:", data);
      // Step 73: Update state with fetched data.
      setDrawdownData(data);
    } catch (error) {
      // Step 74: Handle fetch or processing errors.
      console.error("Error fetching portfolio drawdown:", error);
      setErrorDrawdown(error.message);
      setDrawdownData(null);
    } finally {
      // Step 75: Set loading state to false.
      setIsLoadingDrawdown(false);
    }
  }, []); // No dependencies, this fetch doesn't depend on the benchmark.

  const fetchPortfolioComposition = useCallback(async () => {
    setLoadingComposition(true);
    try {
      const response = await fetch('http://localhost:3002/portfolio-composition');
      const data = await response.json();

      if (response.ok) {
        // Ensure composition is always an array
        setPortfolioComposition(data.composition || []);
      } else {
        console.error('Error fetching portfolio composition:', data.error);
        setPortfolioComposition([]); // Set empty array on error
      }
    } catch (error) {
      console.error('Failed to fetch portfolio composition:', error);
      setPortfolioComposition([]); // Set empty array on error
    } finally {
      setLoadingComposition(false);
    }
  }, []); // No dependencies

  const fetchStyleAnalysis = useCallback(async () => {
    setLoadingStyleAnalysis(true);
    try {
      const response = await fetch('http://localhost:3002/style-analysis');
      const data = await response.json();

      if (response.ok) {
        setStyleAnalysis(data);
      } else {
        console.error('Error fetching style analysis:', data.error);
      }
    } catch (error) {
      console.error('Failed to fetch style analysis:', error);
    } finally {
      setLoadingStyleAnalysis(false);
    }
  }, []); // No dependencies

  const fetchFundamentalsDate = useCallback(async () => {
    setLoadingFundamentalsDate(true);
    try {
      const response = await fetch('http://localhost:3002/fundamentals-date');
      const data = await response.json();

      if (response.ok) {
        setFundamentalsDate(data.fundamentalsDate || '');
      } else {
        console.error('Error fetching fundamentals date:', data.error);
      }
    } catch (error) {
      console.error('Failed to fetch fundamentals date:', error);
    } finally {
      setLoadingFundamentalsDate(false);
    }
  }, []); // No dependencies

  const fetchActiveReturns = useCallback(async () => {
    setLoadingActiveReturns(true);
    try {
      const response = await fetch('http://localhost:3002/active-return');
      const data = await response.json();

      if (response.ok) {
        setActiveReturns(data);
      } else {
        console.error('Error fetching active returns:', data.error);
      }
    } catch (error) {
      console.error('Failed to fetch active returns:', error);
    } finally {
      setLoadingActiveReturns(false);
    }
  }, []); // No dependencies

  const fetchMarketPerformance = useCallback(async () => {
    setLoadingMarketPerformance(true);
    try {
      const response = await fetch('http://localhost:3002/market-performance');
      const data = await response.json();

      if (response.ok) {
        setMarketPerformance(data);
      } else {
        console.error('Error fetching market performance:', data.error);
      }
    } catch (error) {
      console.error('Failed to fetch market performance:', error);
    } finally {
      setLoadingMarketPerformance(false);
    }
  }, []); // No dependencies

  // --- useEffect Hooks for Fetching ---

  // Fetch benchmark-dependent data when benchmark changes
  useEffect(() => {
    // This effect now correctly runs only when selectedBenchmark changes,
    // or if the fetch functions themselves change (which they won't unless
    // their own dependencies change, which is just selectedBenchmark here).
    fetchAnnualReturns();
    fetchMonthlyReturns();
    fetchPortfolioGrowth();
    fetchRiskReturnMetrics();
    // Add other benchmark-dependent fetches here if any
  }, [
      selectedBenchmark, // Primary dependency
      // Add the useCallback-wrapped functions as dependencies
      fetchAnnualReturns,
      fetchMonthlyReturns,
      fetchPortfolioGrowth,
      fetchRiskReturnMetrics
    ]);

  // Fetch non-benchmark, non-upload-dependent data on mount
  useEffect(() => {
    fetchPortfolioComposition(); // Depends on config
    fetchStyleAnalysis(); // Depends on config
    fetchFundamentalsDate(); // Static
    // Data dependent on uploads is fetched in handleUpload
  }, [
      // Add the useCallback-wrapped functions as dependencies
      fetchPortfolioComposition,
      fetchStyleAnalysis,
      fetchFundamentalsDate
    ]); // Runs once on mount, dependencies are stable

  // --- Prepare Annual Returns Chart Data ---
  const annualReturnsChartData = {
    labels: annualReturnsData?.map(item => item.year) || [],
    datasets: [
      {
        label: 'Portfolio Return (%)',
        data: annualReturnsData?.map(item => item.portfolioReturn) || [],
        backgroundColor: 'rgba(255, 0, 255, 0.6)',
        borderColor: '#ff00ff',
        borderWidth: 1,
        barThickness: 'flex',
        maxBarThickness: 50,
      },
      {
        label: `${selectedBenchmark} Return (%)`,
        data: annualReturnsData?.map(item => item.benchmarkReturn) || [],
        backgroundColor: 'rgba(0, 255, 204, 0.6)',
        borderColor: '#00ffcc',
        borderWidth: 1,
        barThickness: 'flex',
        maxBarThickness: 50,
      },
    ],
  };

  // Specific options for the Annual Returns chart
  const annualReturnsChartOptions = {
    ...cyberpunkChartOptions,
    plugins: {
      ...cyberpunkChartOptions.plugins,
      title: {
        ...cyberpunkChartOptions.plugins.title,
        text: `Annual Returns (%) - Portfolio vs. ${selectedBenchmark}`,
      },
      tooltip: {
         ...cyberpunkChartOptions.plugins.tooltip,
         callbacks: {
            label: function(context) {
                let label = context.dataset.label || '';
                if (label) { label += ': '; }
                if (context.parsed.y !== null) {
                    label += context.parsed.y.toFixed(2) + '%';
                }
                return label;
            }
         }
      }
    },
    scales: {
        ...cyberpunkChartOptions.scales,
        y: {
            ...cyberpunkChartOptions.scales.y,
            title: {
                display: true,
                text: 'Return (%)',
                color: '#00ffcc',
                 font: { family: "'Courier New', Courier, monospace" },
            },
            ticks: { // Ensure y-axis ticks are formatted as percentage
                ...cyberpunkChartOptions.scales.y.ticks,
                callback: function(value) { return value + '%'; }
            }
        }
    }
  };

  // --- Prepare Monthly Returns Chart Data ---
  const monthlyReturnsChartData = {
    datasets: [
      {
        label: 'Portfolio Monthly Return (%)',
        data: monthlyReturnsData?.map(item => ({
          x: parse(item.yearMonth, 'yyyy-MM', new Date()),
          y: item.portfolioReturn
        })) || [],
        borderColor: '#ff00ff',
        backgroundColor: 'rgba(255, 0, 255, 0.3)',
        tension: 0.1,
        pointBackgroundColor: '#ff00ff',
        pointRadius: 2,
        pointHoverRadius: 5,
        fill: false,
      },
      {
        label: `${selectedBenchmark} Monthly Return (%)`,
        data: monthlyReturnsData?.map(item => ({
          x: parse(item.yearMonth, 'yyyy-MM', new Date()),
          y: item.benchmarkReturn
        })) || [],
        borderColor: '#00ffcc',
        backgroundColor: 'rgba(0, 255, 204, 0.3)',
        tension: 0.1,
        pointBackgroundColor: '#00ffcc',
        pointRadius: 2,
        pointHoverRadius: 5,
        fill: false,
      },
    ],
  };

  // Specific options for the Monthly Returns chart
  const monthlyReturnsChartOptions = {
    ...cyberpunkChartOptions,
    plugins: {
      ...cyberpunkChartOptions.plugins,
      title: {
        ...cyberpunkChartOptions.plugins.title,
        text: `Monthly Returns (%) - Portfolio vs. ${selectedBenchmark}`,
      },
      tooltip: {
         ...cyberpunkChartOptions.plugins.tooltip,
         callbacks: {
            label: function(context) {
                let label = context.dataset.label || '';
                if (label) { label += ': '; }
                if (context.parsed.y !== null) {
                    label += context.parsed.y.toFixed(2) + '%';
                }
                return label;
            }
         }
      }
    },
    scales: {
      x: {
        type: 'time',
        time: {
          unit: 'month',
          tooltipFormat: 'MMM yyyy',
          displayFormats: {
            month: 'MMM yyyy'
          }
        },
        ticks: {
          color: '#00ffcc',
          font: { family: "'Courier New', Courier, monospace" },
          maxRotation: 0,
          autoSkip: true,
          maxTicksLimit: 10
        },
        grid: {
          color: 'rgba(0, 255, 204, 0.2)',
          borderColor: '#00ffcc',
        },
        title: {
            display: false,
        }
      },
      y: {
        ...cyberpunkChartOptions.scales.y,
        title: {
            ...cyberpunkChartOptions.scales.y.title,
            text: 'Monthly Return (%)',
        },
        ticks: {
          ...cyberpunkChartOptions.scales.y.ticks,
          callback: function(value) {
            return value + '%';
          }
        }
      }
    }
  };

  // --- Prepare Portfolio Growth Chart Data ---
  const portfolioGrowthChartData = {
    datasets: [
      {
        label: 'Portfolio Value',
        data: portfolioGrowthData?.map(item => ({
          x: parse(item.date, 'yyyy-MM-dd', new Date()),
          y: item.portfolioValue
        })) || [],
        borderColor: '#ff00ff',
        backgroundColor: 'rgba(255, 0, 255, 0.1)',
        tension: 0.1,
        pointRadius: 0,
        pointHoverRadius: 5,
        fill: true,
        borderWidth: 2,
      },
      {
        label: `${selectedBenchmark} (Normalized)`,
        data: portfolioGrowthData?.map(item => ({
          x: parse(item.date, 'yyyy-MM-dd', new Date()),
          y: item.benchmarkValue
        })) || [],
        borderColor: '#00ffcc',
        backgroundColor: 'rgba(0, 255, 204, 0.1)',
        tension: 0.1,
        pointRadius: 0,
        pointHoverRadius: 5,
        fill: true,
        borderWidth: 2,
      },
    ],
  };

  // Specific options for the Portfolio Growth chart
  const portfolioGrowthChartOptions = {
    ...cyberpunkChartOptions,
    plugins: {
      ...cyberpunkChartOptions.plugins,
      title: {
        ...cyberpunkChartOptions.plugins.title,
        text: `Portfolio Growth vs. ${selectedBenchmark}`,
      },
      tooltip: {
         ...cyberpunkChartOptions.plugins.tooltip,
         callbacks: {
            title: function(tooltipItems) {
                const date = tooltipItems[0].parsed.x;
                return date ? new Date(date).toLocaleDateString() : '';
            },
            label: function(context) {
                let label = context.dataset.label || '';
                if (label) { label += ': '; }
                if (context.parsed.y !== null) {
                    label += new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(context.parsed.y);
                }
                return label;
            }
         }
      }
    },
    scales: {
      x: {
        type: 'time',
        time: {
          unit: 'month',
          tooltipFormat: 'MMM d, yyyy',
          displayFormats: {
            month: 'MMM yyyy'
          }
        },
        ticks: {
          color: '#00ffcc',
          font: { family: "'Courier New', Courier, monospace" },
          maxRotation: 0,
          autoSkip: true,
          maxTicksLimit: 10
        },
        grid: {
          color: 'rgba(0, 255, 204, 0.2)',
          borderColor: '#00ffcc',
        },
        title: {
            display: false,
        }
      },
      y: {
        ...cyberpunkChartOptions.scales.y,
        title: {
            ...cyberpunkChartOptions.scales.y.title,
            text: 'Value (USD)',
        },
        ticks: {
          ...cyberpunkChartOptions.scales.y.ticks,
          callback: function(value) {
            return new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD',
                notation: 'compact',
                maximumFractionDigits: 0,
                minimumFractionDigits: 0
             }).format(value);
          }
        }
      }
    }
  };

  // --- Prepare Drawdown Chart Data ---
  const drawdownChartData = {
    datasets: [
      {
        label: 'Portfolio Drawdown (%)',
        data: drawdownData?.map(item => ({
          x: parse(item.date, 'yyyy-MM-dd', new Date()), // Parse 'YYYY-MM-DD'
          y: item.drawdownPercentage // Should be negative or zero
        })) || [],
        borderColor: '#ff4500', // Orange-red color for drawdown
        backgroundColor: 'rgba(255, 69, 0, 0.2)', // Semi-transparent orange-red fill
        tension: 0.1,
        pointRadius: 0, // Hide points
        pointHoverRadius: 5,
        fill: true, // Fill area below the line (up to 0)
        borderWidth: 2,
        stepped: false, // Use 'stepped: true' for a stepped line if preferred
      },
    ],
  };

  // Specific options for the Drawdown chart
  const drawdownChartOptions = {
    ...cyberpunkChartOptions, // Inherit base styles
    plugins: {
      ...cyberpunkChartOptions.plugins,
      legend: { // Hide legend as there's only one dataset
          display: false,
      },
      title: {
        ...cyberpunkChartOptions.plugins.title,
        text: 'Portfolio Drawdown Over Time',
        color: '#ff4500', // Match line color
      },
      tooltip: {
         ...cyberpunkChartOptions.plugins.tooltip,
         borderColor: '#ff4500', // Match line color
         titleColor: '#ff4500', // Match line color
         callbacks: {
            // Format tooltip title (date)
            title: function(tooltipItems) {
                const date = tooltipItems[0].parsed.x;
                return date ? new Date(date).toLocaleDateString() : '';
            },
            // Format tooltip body (value) as percentage
            label: function(context) {
                let label = context.dataset.label || '';
                if (label) { label += ': '; }
                if (context.parsed.y !== null) {
                    // Format as percentage with 2 decimal places
                    label += context.parsed.y.toFixed(2) + '%';
                }
                return label;
            }
         }
      }
    },
    scales: {
      x: { // Override x-axis for time scale
        type: 'time',
        time: {
          unit: 'month', // Adjust unit based on data span if needed
          tooltipFormat: 'MMM d, yyyy',
          displayFormats: { month: 'MMM yyyy' }
        },
        ticks: {
          color: '#00ffcc',
          font: { family: "'Courier New', Courier, monospace" },
          maxRotation: 0, autoSkip: true, maxTicksLimit: 10
        },
        grid: { color: 'rgba(0, 255, 204, 0.2)', borderColor: '#00ffcc' },
        title: { display: false }
      },
      y: { // Override y-axis for percentage formatting
        ...cyberpunkChartOptions.scales.y, // Inherit base y-axis styles
        suggestedMin: -50, // Suggest a minimum, adjust as needed
        suggestedMax: 0,   // Max drawdown is 0%
        title: {
            ...cyberpunkChartOptions.scales.y.title,
            text: 'Drawdown (%)', // Y-axis title
            color: '#ff4500', // Match line color
        },
        ticks: {
          ...cyberpunkChartOptions.scales.y.ticks,
          color: '#ff4500', // Match line color for ticks
          // Format y-axis labels as percentage
          callback: function(value) {
            return value.toFixed(0) + '%'; // Format as integer percentage
          }
        },
        grid: {
            color: 'rgba(255, 69, 0, 0.2)', // Faint orange-red grid lines
            borderColor: '#ff4500', // Match line color for axis line
        },
      }
    }
  };

  // --- Prepare Asset Allocation Pie Chart Data ---
  const assetAllocationChartData = {
    labels: portfolioComposition?.map(asset => asset.ticker) || [],
    datasets: [
      {
        label: 'Allocation %',
        data: portfolioComposition?.map(asset => asset.allocation_percentage) || [],
        backgroundColor: portfolioComposition?.map((_, index) =>
          cyberpunkPieColors[index % cyberpunkPieColors.length] // Cycle through colors
        ) || [],
        borderColor: '#000000', // Black border for contrast
        borderWidth: 2,
        hoverOffset: 8, // Slightly enlarge slice on hover
        hoverBorderColor: '#ffffff', // White border on hover
      },
    ],
  };

  // Specific options for the Asset Allocation Pie chart
  const assetAllocationChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'right', // Position legend to the right
        labels: {
          color: '#00ffcc', // Neon teal/cyan for legend text
          font: {
            family: "'Courier New', Courier, monospace",
          },
          boxWidth: 15, // Size of the color box
          padding: 15, // Padding between legend items
        },
      },
      title: {
        display: true,
        text: 'Asset Allocation',
        color: '#ffff00', // Neon Yellow title
        font: {
          size: 18,
          family: "'Courier New', Courier, monospace",
        },
        padding: {
            bottom: 20 // Add padding below title
        }
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        titleColor: '#ffff00', // Match title color
        bodyColor: '#00ffcc',
        borderColor: '#ffff00', // Match title color
        borderWidth: 1,
        titleFont: { family: "'Courier New', Courier, monospace" },
        bodyFont: { family: "'Courier New', Courier, monospace" },
        callbacks: {
          // Format tooltip label to show Ticker: Percentage%
          label: function(context) {
            let label = context.label || ''; // Ticker symbol
            let value = context.parsed || 0;
            if (label) {
              label += ': ';
            }
            label += value.toFixed(2) + '%';
            return label;
          },
          // Hide title in tooltip as label is sufficient
          title: function() {
              return null;
          }
        },
      },
    },
    // No scales needed for Pie charts
  };

  // --- JSX Rendering --- 
  // This is the structure of the web page displayed to the user.

  // Step 87: Render the main application UI.
  return (
    // Main container div: sets background, text color, font, padding, and centers content.
    <div className="min-h-screen bg-black text-neon-green font-mono p-4 md:p-8 flex flex-col items-center">
      
      {/* Header Section */}
      // Contains the main title and subtitle.
      <header className="w-full max-w-7xl mb-8">
        {/* Main title with large text, bold, specific color, margin, and glow effect. */}
        <h1 className="text-4xl md:text-5xl font-bold text-neon-pink mb-4 text-center glow-pink">Robinhood Dashboard</h1>
        {/* Subtitle with specific color and size. */}
        <p className="text-center text-neon-cyan text-lg">Upload your Robinhood CSV to visualize your portfolio performance.</p>
      </header>

      {/* Upload Section */}
      // Contains the file input and upload button.
      <section className="w-full max-w-2xl bg-gray-900 p-6 rounded-lg shadow-lg border border-neon-cyan mb-8 glow-border-cyan">
        {/* Section title. */}
        <h2 className="text-2xl font-semibold text-neon-magenta mb-4 text-center">Upload Transactions</h2>
        {/* Flex container for input and button, arranges them in a row on larger screens. */}
        <div className="flex flex-col sm:flex-row items-center justify-center space-y-4 sm:space-y-0 sm:space-x-4">
          {/* File input element. */}
          <input 
            type="file" // Specifies this is a file input.
            accept=".csv" // Restricts accepted file types to CSV.
            onChange={handleFileChange} // Calls handleFileChange when a file is selected.
            // Styling for the file input button and text.
            className="file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-neon-pink file:text-black hover:file:bg-neon-magenta cursor-pointer text-neon-cyan" 
          />
          {/* Upload button. */}
          <button 
            onClick={handleUpload} // Calls handleUpload when clicked.
            disabled={isLoading || !file} // Button is disabled if loading or no file is selected.
            // Dynamic styling based on disabled state (grayed out) or active state (neon cyan with hover effect).
            className={`py-2 px-6 rounded-full font-semibold text-black transition duration-300 ease-in-out ${isLoading || !file ? 'bg-gray-600 cursor-not-allowed' : 'bg-neon-cyan hover:bg-cyan-300 shadow-md glow-button-cyan'}`}
          >
            {/* Button text changes based on loading state. */}
            {isLoading ? 'Uploading...' : 'Upload CSV'}
          </button>
        </div>
        {/* Display Upload Status Message */}
        // Conditionally render the status message if uploadStatus is not null.
        {uploadStatus && (
          // Paragraph styling changes color based on status type (error=red, warning=yellow, success=green).
          <p className={`mt-4 text-center font-semibold ${uploadStatus.type === 'error' ? 'text-red-500' : (uploadStatus.type === 'warning' ? 'text-yellow-500' : 'text-green-500')}`}>
            {uploadStatus.message} {/* Display the message from the uploadStatus state. */}
          </p>
        )}
      </section>

      {/* Benchmark Selection Dropdown */}
      // Allows the user to choose a benchmark index for comparison.
      <section className="w-full max-w-md bg-gray-900 p-4 rounded-lg shadow-lg border border-neon-orange mb-8 glow-border-orange">
          {/* Label for the dropdown. */}
          <label htmlFor="benchmark-select" className="block text-neon-orange font-semibold mb-2 text-center">Select Benchmark:</label>
          {/* Dropdown select element. */}
          <select 
              id="benchmark-select" 
              value={selectedBenchmark} // The current value is bound to the selectedBenchmark state.
              onChange={(e) => setSelectedBenchmark(e.target.value)} // Update state when selection changes, triggering data refetches via useEffect.
              // Styling for the dropdown.
              className="w-full p-2 rounded bg-gray-800 border border-neon-orange text-neon-cyan focus:outline-none focus:ring-2 focus:ring-neon-orange font-mono"
          >
              {/* Benchmark options. */}
              <option value="SPY">SPY (S&P 500 ETF)</option>
              <option value="QQQ">QQQ (Nasdaq 100 ETF)</option>
              <option value="DIA">DIA (Dow Jones ETF)</option>
              <option value="VT">VT (Vanguard Total World Stock ETF)</option>
          </select>
      </section>

      {/* Main Content Area - Display Charts and Data */}
      // Uses a CSS grid layout to arrange the different data visualization components.
      <main className="w-full max-w-7xl grid grid-cols-1 md:grid-cols-2 gap-8">
        
        {/* Portfolio Growth Chart Section */}
        // Takes full width on medium screens and above (md:col-span-2).
        // Sets a fixed height (h-96) for the chart container.
        <div className="bg-gray-900 p-4 rounded-lg shadow-lg border border-neon-cyan glow-border-cyan md:col-span-2 h-96">
          {/* Chart title. */}
          <h3 className="text-xl font-semibold text-neon-magenta mb-2 text-center">Portfolio Growth</h3>
          {/* Conditional rendering based on loading/error/data state for this chart. */}
          {isLoadingPortfolioGrowth ? (
            <p className="text-center text-neon-cyan">Loading growth data...</p> // Show loading message.
          ) : errorPortfolioGrowth ? (
            <p className="text-center text-red-500">Error: {errorPortfolioGrowth}</p> // Show error message.
          ) : portfolioGrowthData ? (
            // If data exists, render the chart container.
            // pb-8 adds padding at the bottom to prevent axis labels from being cut off.
            <div className="h-full pb-8">
              {/* Render the Line chart component with its options and data. */}
              <Line options={portfolioGrowthChartOptions} data={portfolioGrowthChartData} />
            </div>
          ) : (
            <p className="text-center text-gray-500">Upload CSV to see portfolio growth.</p> // Default message if no data.
          )}
        </div>

        {/* Annual Returns Chart Section */}
        // Sets a fixed height (h-80).
        <div className="bg-gray-900 p-4 rounded-lg shadow-lg border border-neon-orange glow-border-orange h-80">
          <h3 className="text-xl font-semibold text-neon-magenta mb-2 text-center">Annual Returns</h3>
          {/* Conditional rendering for loading/error/data states. */}
          {isLoadingAnnualReturns ? (
            <p className="text-center text-neon-cyan">Loading annual returns...</p>
          ) : errorAnnualReturns ? (
            <p className="text-center text-red-500">Error: {errorAnnualReturns}</p>
          ) : annualReturnsData ? (
            <div className="h-full pb-8">
              {/* Render the Bar chart component. */}
               <Bar options={annualReturnsChartOptions} data={annualReturnsChartData} />
            </div>
           ) : (
            <p className="text-center text-gray-500">Upload CSV to see annual returns.</p>
          )}
        </div>
        
        {/* Drawdown Chart Section */}
        // Sets a fixed height (h-80).
        <div className="bg-gray-900 p-4 rounded-lg shadow-lg border border-red-600 glow-border-red h-80">
           <h3 className="text-xl font-semibold text-neon-magenta mb-2 text-center">Portfolio Drawdown</h3>
           {/* Conditional rendering for loading/error/data states. */}
           {isLoadingDrawdown ? (
            <p className="text-center text-neon-cyan">Loading drawdown data...</p>
          ) : errorDrawdown ? (
            <p className="text-center text-red-500">Error: {errorDrawdown}</p>
          ) : drawdownData ? (
            <div className="h-full pb-8">
              {/* Render the Line chart component for drawdown. */}
              <Line options={drawdownChartOptions} data={drawdownChartData} />
            </div>
          ) : (
            <p className="text-center text-gray-500">Upload CSV to see drawdown.</p>
          )}
        </div>

        {/* Risk/Return Metrics Table Section */}
        // Takes full width on medium screens and above.
        <div className="bg-gray-900 p-4 rounded-lg shadow-lg border border-neon-yellow glow-border-yellow md:col-span-2">
           <h3 className="text-xl font-semibold text-neon-magenta mb-2 text-center">Risk & Return Metrics</h3>
           {/* Conditional rendering for loading/data state. */}
            {loadingRiskReturn ? (
              <p className="text-center text-neon-cyan">Loading metrics...</p>
            ) : riskReturnMetrics ? (
              // Container to allow horizontal scrolling on small screens if table is wide.
              <div className="overflow-x-auto">
                 {/* Table for displaying metrics. */}
                 <table className="w-full text-left border-collapse">
                    <thead>
                      {/* Table header row. */}
                      <tr className="border-b border-neon-yellow">
                        <th className="p-2 text-neon-yellow">Metric</th>
                        <th className="p-2 text-neon-yellow">Portfolio</th>
                        <th className="p-2 text-neon-yellow">Benchmark ({selectedBenchmark})</th>
                      </tr>
                    </thead>
                    <tbody>
                      {/* Map through the key-value pairs in the riskReturnMetrics object. */}
                      {Object.entries(riskReturnMetrics).map(([key, values]) => (
                         // Create a table row for each metric.
                         <tr key={key} className="border-b border-gray-700 hover:bg-gray-800">
                           {/* Metric name (replace underscores with spaces, capitalize). */}
                           <td className="p-2 text-neon-cyan capitalize">{key.replace(/_/g, ' ')}</td>
                           {/* Portfolio value (format as number if possible). */}
                           <td className="p-2">{typeof values.portfolio === 'number' ? values.portfolio.toFixed(2) : values.portfolio}</td>
                           {/* Benchmark value (format as number if possible). */}
                           <td className="p-2">{typeof values.benchmark === 'number' ? values.benchmark.toFixed(2) : values.benchmark}</td>
                         </tr>
                      ))}
                    </tbody>
                 </table>
               </div>
            ) : (
              <p className="text-center text-gray-500">Upload CSV to see metrics.</p> // Default message.
            )}
        </div>
        
         {/* Asset Allocation Pie Chart Section */}
         // Sets a fixed height (h-80).
         <div className="bg-gray-900 p-4 rounded-lg shadow-lg border border-purple-500 glow-border-purple h-80">
           <h3 className="text-xl font-semibold text-neon-magenta mb-2 text-center">Asset Allocation</h3>
           {/* Conditional rendering. Note: portfolioComposition data fetching is missing/commented out. */}
           {loadingComposition ? (
             <p className="text-center text-neon-cyan">Loading allocation...</p>
           ) : portfolioComposition.length > 0 ? (
             // If data existed, the Pie chart would render here.
             <div className="h-full pb-8">
               <Pie options={assetAllocationChartOptions} data={assetAllocationChartData} />
             </div>
           ) : (
             // Default message shown because data fetching isn't implemented yet.
             <p className="text-center text-gray-500">Portfolio composition data unavailable.</p>
           )}
         </div>

        {/* Holdings Based Style Analysis Table Section */}
        <div className="bg-gray-900 p-4 rounded-lg shadow-lg border border-green-500 glow-border-green md:col-span-2">
          <h3 className="text-xl font-semibold text-neon-magenta mb-4 text-center">Holdings Based Style Analysis</h3>
          {loadingStyleAnalysis ? (
            <p className="text-center text-neon-cyan">Loading style analysis...</p>
          ) : styleAnalysis?.styleAnalysis?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm mb-6">
                <thead>
                  <tr className="border-b border-green-500">
                    <th className="p-2 text-green-400">Ticker</th>
                    <th className="p-2 text-green-400">Category</th>
                    <th className="p-2 text-green-400 text-right">Weight (%)</th>
                    <th className="p-2 text-green-400 text-right">Yield (SEC)</th>
                    <th className="p-2 text-green-400 text-right">Yield (TTM)</th>
                    <th className="p-2 text-green-400 text-right">Expense (Net)</th>
                    <th className="p-2 text-green-400 text-right">Expense (Gross)</th>
                    <th className="p-2 text-green-400 text-right">P/E</th>
                    <th className="p-2 text-green-400 text-right">Duration</th>
                    <th className="p-2 text-green-400 text-right">Contrib. Return (%)</th>
                    <th className="p-2 text-green-400 text-right">Contrib. Risk (%)</th>
                  </tr>
                </thead>
                <tbody>
                  {styleAnalysis.styleAnalysis.map((item, index) => (
                    <tr key={index} className="border-b border-gray-700 hover:bg-gray-800">
                      <td className="p-2 font-semibold text-neon-cyan">{item.ticker}</td>
                      <td className="p-2">{item.category}</td>
                      <td className="p-2 text-right">{item.weight}</td>
                      <td className="p-2 text-right">{item.secYield}</td>
                      <td className="p-2 text-right">{item.ttmYield}</td>
                      <td className="p-2 text-right">{item.netExpenseRatio}</td>
                      <td className="p-2 text-right">{item.grossExpenseRatio}</td>
                      <td className="p-2 text-right">{item.peRatio}</td>
                      <td className="p-2 text-right">{item.duration}</td>
                      <td className="p-2 text-right">{item.contributionToReturn}</td>
                      <td className="p-2 text-right">{item.contributionToRisk}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              
              {/* Display Portfolio Totals */}
              {styleAnalysis.portfolioTotals && (
                <div>
                   <h4 className="text-lg font-semibold text-neon-yellow mb-2">Portfolio Totals</h4>
                   <div className="grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-1 text-sm">
                      <span className="text-neon-cyan">Total SEC Yield:</span><span>{styleAnalysis.portfolioTotals.totalSecYield}%</span>
                      <span className="text-neon-cyan">Total TTM Yield:</span><span>{styleAnalysis.portfolioTotals.totalTtmYield}%</span>
                      <span className="text-neon-cyan">Total Net Expense Ratio:</span><span>{styleAnalysis.portfolioTotals.totalNetExpenseRatio}%</span>
                      <span className="text-neon-cyan">Total Gross Expense Ratio:</span><span>{styleAnalysis.portfolioTotals.totalGrossExpenseRatio}%</span>
                      <span className="text-neon-cyan">Total P/E:</span><span>{styleAnalysis.portfolioTotals.totalPeRatio}</span>
                      <span className="text-neon-cyan">Total Duration:</span><span>{styleAnalysis.portfolioTotals.totalDuration}</span>
                      <span className="text-neon-cyan">Total Contribution to Return:</span><span>{styleAnalysis.portfolioTotals.totalContributionToReturn}%</span>
                   </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-center text-gray-500">Style analysis data unavailable. (May require portfolio configuration)</p>
          )}
        </div>

        {/* Active Return Contribution Table Section */}
        <div className="bg-gray-900 p-4 rounded-lg shadow-lg border border-blue-500 glow-border-blue md:col-span-2">
          <h3 className="text-xl font-semibold text-neon-magenta mb-4 text-center">Active Return Contribution</h3>
          {loadingActiveReturns ? (
            <p className="text-center text-neon-cyan">Loading active returns...</p>
          ) : activeReturns?.activeReturns?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-blue-500">
                    <th className="p-2 text-blue-400">Ticker</th>
                    {activeReturns.activeReturns[0].returns.map(periodData => (
                      <th key={periodData.period} className="p-2 text-blue-400 text-right">{periodData.period} (%)</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {activeReturns.activeReturns.map((assetData, index) => (
                    <tr key={index} className="border-b border-gray-700 hover:bg-gray-800">
                      <td className="p-2 font-semibold text-neon-cyan">{assetData.ticker}</td>
                      {assetData.returns.map(periodData => (
                        <td key={periodData.period} className="p-2 text-right">{periodData.activeReturn}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-center text-gray-500">Active return data unavailable.</p>
          )}
        </div>

        {/* Up vs. Down Market Performance Table Section */}
        <div className="bg-gray-900 p-4 rounded-lg shadow-lg border border-yellow-500 glow-border-yellow md:col-span-2">
          <h3 className="text-xl font-semibold text-neon-magenta mb-4 text-center">Up vs. Down Market Performance vs. {selectedBenchmark}</h3>
          {loadingMarketPerformance ? (
            <p className="text-center text-neon-cyan">Loading market performance...</p>
          ) : marketPerformance?.marketPerformance?.length > 0 ? (
             <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="border-b border-yellow-500">
                    <th className="p-2 text-yellow-400">Market Type</th>
                    <th className="p-2 text-yellow-400 text-right">Occurrences</th>
                    <th className="p-2 text-yellow-400 text-right">% Above Benchmark</th>
                    <th className="p-2 text-yellow-400 text-right">Avg Active Return Above Benchmark (%)</th>
                    <th className="p-2 text-yellow-400 text-right">Avg Active Return Below Benchmark (%)</th>
                    <th className="p-2 text-yellow-400 text-right">Total Avg Active Return (%)</th>
                  </tr>
                </thead>
                <tbody>
                  {marketPerformance.marketPerformance.map((item, index) => (
                    <tr key={index} className="border-b border-gray-700 hover:bg-gray-800">
                      <td className="p-2 font-semibold text-neon-cyan">{item.marketType}</td>
                      <td className="p-2 text-right">{item.occurrences}</td>
                      <td className="p-2 text-right">{item.percentageAboveBenchmark}</td>
                      <td className="p-2 text-right">{item.averageActiveReturnAboveBenchmark}</td>
                      <td className="p-2 text-right">{item.averageActiveReturnBelowBenchmark}</td>
                      <td className="p-2 text-right">{item.totalAverageActiveReturn}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-center text-gray-500">Market performance data unavailable.</p>
          )}
        </div>

        {/* Monthly Returns Chart Section */}
        <div className="bg-gray-900 p-4 rounded-lg shadow-lg border border-teal-500 glow-border-teal md:col-span-2 h-96">
           <h3 className="text-xl font-semibold text-neon-magenta mb-2 text-center">Monthly Returns</h3>
           {isLoadingMonthlyReturns ? (
            <p className="text-center text-neon-cyan">Loading monthly returns...</p>
          ) : errorMonthlyReturns ? (
            <p className="text-center text-red-500">Error: {errorMonthlyReturns}</p>
          ) : monthlyReturnsData ? (
            <div className="h-full pb-8">
              <Line options={monthlyReturnsChartOptions} data={monthlyReturnsChartData} />
            </div>
          ) : (
            <p className="text-center text-gray-500">Upload CSV to see monthly returns.</p>
          )}
        </div>

      </main>

      {/* Footer Section */}
      <footer className="w-full max-w-7xl mt-12 pt-4 border-t border-gray-700 text-center text-gray-500 text-sm">
        <p>Robinhood Dashboard | Data for informational purposes only.</p>
        {loadingFundamentalsDate ? (
            <p>Loading data date...</p>
        ) : fundamentalsDate && (
             <p>Fundamentals Data Date: {fundamentalsDate}</p>
        )}
        <p>Stock data provided by Alpha Vantage. Use responsibly.</p>
      </footer>
    </div>
  );
}

// Step 88: Export the App component to be used in main.jsx.
export default App;