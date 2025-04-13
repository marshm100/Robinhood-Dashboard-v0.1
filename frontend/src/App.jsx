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
  const [file, setFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  
  // Comment out unused state variables related to portfolio configuration
  // const [totalInvestment, setTotalInvestment] = useState('');
  // const [allocations, setAllocations] = useState([{ ticker: '', allocation_percentage: '' }]);
  // const [configStatus, setConfigStatus] = useState(null);
  // const [configLoading, setConfigLoading] = useState(false);
  
  const [portfolioComposition, setPortfolioComposition] = useState([]);
  const [loadingComposition, setLoadingComposition] = useState(false);
  const [styleAnalysis, setStyleAnalysis] = useState({ styleAnalysis: [], portfolioTotals: {} });
  const [loadingStyleAnalysis, setLoadingStyleAnalysis] = useState(false);
  const [fundamentalsDate, setFundamentalsDate] = useState('');
  const [loadingFundamentalsDate, setLoadingFundamentalsDate] = useState(false);
  const [activeReturns, setActiveReturns] = useState({ activeReturns: [] });
  const [loadingActiveReturns, setLoadingActiveReturns] = useState(false);
  const [marketPerformance, setMarketPerformance] = useState({ marketPerformance: [] });
  const [loadingMarketPerformance, setLoadingMarketPerformance] = useState(false);
  const [riskReturnMetrics, setRiskReturnMetrics] = useState(null);
  const [loadingRiskReturn, setLoadingRiskReturn] = useState(false);
  const [annualReturnsData, setAnnualReturnsData] = useState(null);
  const [isLoadingAnnualReturns, setIsLoadingAnnualReturns] = useState(true);
  const [errorAnnualReturns, setErrorAnnualReturns] = useState(null);
  const [monthlyReturnsData, setMonthlyReturnsData] = useState(null);
  const [isLoadingMonthlyReturns, setIsLoadingMonthlyReturns] = useState(true);
  const [errorMonthlyReturns, setErrorMonthlyReturns] = useState(null);
  const [portfolioGrowthData, setPortfolioGrowthData] = useState(null);
  const [isLoadingPortfolioGrowth, setIsLoadingPortfolioGrowth] = useState(true);
  const [errorPortfolioGrowth, setErrorPortfolioGrowth] = useState(null);
  const [selectedBenchmark, setSelectedBenchmark] = useState('SPY'); // Default benchmark
  const [drawdownData, setDrawdownData] = useState(null);
  const [isLoadingDrawdown, setIsLoadingDrawdown] = useState(true);
  const [errorDrawdown, setErrorDrawdown] = useState(null);

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

  const fetchAnnualReturns = useCallback(async () => {
    setIsLoadingAnnualReturns(true);
    setErrorAnnualReturns(null);
    try {
      const response = await fetch(`http://localhost:3002/annual-returns?benchmark=${selectedBenchmark}`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      setAnnualReturnsData(data);
    } catch (error) {
      console.error("Error fetching annual returns:", error);
      setErrorAnnualReturns(error.message);
      setAnnualReturnsData(null);
    } finally {
      setIsLoadingAnnualReturns(false);
    }
  }, [selectedBenchmark]); // Dependency: selectedBenchmark

  const fetchMonthlyReturns = useCallback(async () => {
    setIsLoadingMonthlyReturns(true);
    setErrorMonthlyReturns(null);
    try {
      const response = await fetch(`http://localhost:3002/monthly-returns?benchmark=${selectedBenchmark}`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      setMonthlyReturnsData(data);
    } catch (error) {
      console.error("Error fetching monthly returns:", error);
      setErrorMonthlyReturns(error.message);
      setMonthlyReturnsData(null);
    } finally {
      setIsLoadingMonthlyReturns(false);
    }
  }, [selectedBenchmark]); // Dependency: selectedBenchmark

  const fetchPortfolioGrowth = useCallback(async () => {
    setIsLoadingPortfolioGrowth(true);
    setErrorPortfolioGrowth(null);
    console.log(`Fetching portfolio growth data with benchmark: ${selectedBenchmark}`);
    try {
      const response = await fetch(`http://localhost:3002/portfolio-growth?benchmark=${selectedBenchmark}`);
      if (!response.ok) {
        // Show proper error message instead of using fallback data
        console.error(`Error fetching portfolio growth data: ${response.status}`);
        setErrorPortfolioGrowth('Failed to fetch portfolio data. Please upload transactions first.');
        setPortfolioGrowthData(null);
        return;
      }
      
      const data = await response.json();
      console.log("Fetched Portfolio Growth Data:", data);
      
      if (!Array.isArray(data) || data.length === 0) {
        console.warn("Fetched portfolio growth data is empty or not an array");
        setErrorPortfolioGrowth('No portfolio data available. Please upload transactions first.');
        setPortfolioGrowthData(null);
        return;
      }
      
      if (!Object.hasOwn(data[0], 'portfolioValue') || !Object.hasOwn(data[0], 'benchmarkValue')) {
        console.warn("Fetched portfolio growth data is not in the expected format");
        // Parse or transform the data to the expected format
        const transformedData = data.map(item => ({
          date: item.date || new Date().toISOString().split('T')[0],
          portfolioValue: item.portfolioValue || item.value || 0,
          benchmarkValue: item.benchmarkValue || 0
        }));
        
        setPortfolioGrowthData(transformedData);
      } else {
        setPortfolioGrowthData(data);
      }
    } catch (error) {
      console.error("Error fetching portfolio growth:", error);
      setErrorPortfolioGrowth(error.message);
      setPortfolioGrowthData(null);
    } finally {
      setIsLoadingPortfolioGrowth(false);
    }
  }, [selectedBenchmark]); // Dependency: selectedBenchmark

  const fetchRiskReturnMetrics = useCallback(async () => {
    setLoadingRiskReturn(true);
    try {
      const response = await fetch(`http://localhost:3002/risk-return?benchmark=${selectedBenchmark}`);
      
      if (!response.ok) {
        console.error(`Error fetching risk-return metrics: ${response.status}`);
        setRiskReturnMetrics(null);
        return;
      }
      
      const data = await response.json();

      if (data && data.metrics) {
        setRiskReturnMetrics(data.metrics);
      } else if (data && data.error) {
        console.error('Error from risk-return endpoint:', data.error);
        setRiskReturnMetrics(null);
      } else {
        console.error('Unexpected response format from risk-return endpoint');
        setRiskReturnMetrics(null);
      }
    } catch (error) {
      console.error('Failed to fetch risk and return metrics:', error);
      setRiskReturnMetrics(null);
    } finally {
      setLoadingRiskReturn(false);
    }
  }, [selectedBenchmark]);

  const fetchDrawdownData = useCallback(async () => {
    setIsLoadingDrawdown(true);
    setErrorDrawdown(null);
    console.log("Fetching portfolio drawdown data...");
    try {
      const response = await fetch(`http://localhost:3002/portfolio-drawdown`);
      if (!response.ok) {
        console.error(`Error fetching portfolio drawdown data: ${response.status}`);
        setErrorDrawdown('Failed to fetch drawdown data. Please upload transactions first.');
        setDrawdownData(null);
        return;
      }
      
      const data = await response.json();
      console.log("Fetched Drawdown Data:", data);
      
      if (!Array.isArray(data) || data.length === 0) {
        console.warn("Fetched drawdown data is empty or not an array");
        setErrorDrawdown('No drawdown data available. Please upload transactions first.');
        setDrawdownData(null);
        return;
      }
      
      if (!Object.hasOwn(data[0], 'drawdownPercentage')) {
        console.warn("Fetched drawdown data is not in the expected format");
        
        // Try to transform the data to the expected format
        const transformedData = data.map(item => {
          const value = item.value || 0;
          const peak = item.peak || value;
          
          return {
            date: item.date || new Date().toISOString().split('T')[0],
            value: value,
            peak: peak,
            drawdownPercentage: peak > 0 ? ((peak - value) / peak) * 100 : 0
          };
        });
        
        setDrawdownData(transformedData);
      } else {
        setDrawdownData(data);
      }
    } catch (error) {
      console.error("Error fetching drawdown data:", error);
      setErrorDrawdown(error.message);
      setDrawdownData(null);
    } finally {
      setIsLoadingDrawdown(false);
    }
  }, []); // No dependencies

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

  // Comment out the unused portfolio configuration functions
  /*
  // Submit portfolio configuration
  const handlePortfolioConfigSubmit = async (e) => {
    e.preventDefault();
    
    // Validate inputs
    if (!totalInvestment || isNaN(parseFloat(totalInvestment)) || parseFloat(totalInvestment) <= 0) {
      setConfigStatus({
        type: 'error',
        message: 'Please enter a valid total investment amount.'
      });
      return;
    }
    
    // Filter out incomplete allocations
    const validAllocations = allocations.filter(
      alloc => alloc.ticker && alloc.allocation_percentage && !isNaN(parseFloat(alloc.allocation_percentage))
    );
    
    if (validAllocations.length === 0) {
      setConfigStatus({
        type: 'error',
        message: 'Please add at least one valid allocation.'
      });
      return;
    }
    
    // Check if allocations sum to 100%
    const totalPercentage = validAllocations.reduce(
      (sum, alloc) => sum + parseFloat(alloc.allocation_percentage), 0
    );
    
    if (Math.abs(totalPercentage - 100) > 0.01) { // Allow for small floating point errors
      setConfigStatus({
        type: 'error',
        message: `Allocation percentages must add up to 100%. Current total: ${totalPercentage.toFixed(2)}%`
      });
      return;
    }
    
    setConfigLoading(true);
    setConfigStatus(null);
    
    try {
      const response = await fetch('http://localhost:3002/portfolio-config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          total_investment: parseFloat(totalInvestment),
          allocations: validAllocations.map(alloc => ({
            ticker: alloc.ticker.toUpperCase(),
            allocation_percentage: parseFloat(alloc.allocation_percentage)
          }))
        }),
      });
      
      const result = await response.json();
      
      if (!response.ok) {
        throw new Error(result.error || 'Failed to save portfolio configuration');
      }
      
      setConfigStatus({
        type: 'success',
        message: 'Portfolio configuration saved successfully!'
      });
      
      // Fetch updated portfolio composition and style analysis
      fetchPortfolioComposition();
      fetchStyleAnalysis();
      fetchRiskReturnMetrics();
    } catch (error) {
      console.error('Error saving portfolio configuration:', error);
      setConfigStatus({
        type: 'error',
        message: `Error: ${error.message}`
      });
    } finally {
      setConfigLoading(false);
    }
  };
  */

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

  return (
    <div className="min-h-screen bg-black text-[#00ffcc] font-mono p-4 md:p-8 overflow-x-hidden">
      <header className="mb-8 text-center">
        <h1 className="text-3xl md:text-5xl font-bold text-[#ff00ff] mb-4" style={{ textShadow: '0 0 5px #ff00ff, 0 0 10px #ff00ff' }}>
          Robinhood Dashboard
        </h1>

        <div className="max-w-xs mx-auto mb-6">
            <label htmlFor="benchmark-select" className="block text-sm font-medium text-[#00ffcc] mb-1">Select Benchmark:</label>
            <select
                id="benchmark-select"
                value={selectedBenchmark}
                onChange={(e) => setSelectedBenchmark(e.target.value)}
                className="w-full p-2 bg-gray-800 border border-[#00ffcc] rounded-md text-[#00ffcc] focus:outline-none focus:ring-2 focus:ring-[#ff00ff] appearance-none text-center font-mono"
                style={{
                    backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%2300ffcc' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`,
                    backgroundPosition: 'right 0.5rem center',
                    backgroundRepeat: 'no-repeat',
                    backgroundSize: '1.5em 1.5em',
                    paddingRight: '2.5rem' // Make space for the arrow
                }}
            >
                <option value="SPY">S&P 500 (SPY)</option>
                <option value="QQQ">Nasdaq 100 (QQQ)</option>
                <option value="VT">Total World Stock (VT)</option>
                <option value="AGG">US Aggregate Bond (AGG)</option>
                {/* Add more benchmarks as needed */}
            </select>
        </div>

        <div className="bg-gray-900 p-4 rounded-lg shadow-[0_0_10px_rgba(0,255,204,0.4)] border border-[#00ffcc] max-w-md mx-auto mb-8">
             <h2 className="text-lg text-[#00ffcc] mb-2">Upload Transactions</h2>
             <input type="file" accept=".csv" onChange={handleFileChange} className="text-sm mb-2 file:bg-[#00ffcc] file:border-0 file:text-black file:font-mono file:p-1 file:rounded" />
             <button onClick={handleUpload} disabled={!file || isLoading} className="bg-[#ff00ff] text-black font-bold py-1 px-3 rounded hover:bg-opacity-80 disabled:opacity-50 font-mono">
                 {isLoading ? 'Uploading...' : 'Upload'}
             </button>
             {uploadStatus && <p className={`mt-2 text-xs ${uploadStatus.type === 'success' ? 'text-green-400' : 'text-red-400'}`}>{uploadStatus.message || ''}</p>}
         </div>

      </header>

      <main className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        <section className="bg-gray-900 p-4 rounded-lg shadow-[0_0_15px_rgba(255,0,255,0.5)] border border-[#ff00ff]">
          <h2 className="text-xl text-[#ff00ff] mb-4 text-center">Portfolio Growth</h2>
          <div className="relative h-72 md:h-96">
            {isLoadingPortfolioGrowth && <p className="text-center text-lg animate-pulse">Loading Growth Data...</p>}
            {errorPortfolioGrowth && <p className="text-center text-red-500">Error: {errorPortfolioGrowth}</p>}
            {!isLoadingPortfolioGrowth && !errorPortfolioGrowth && portfolioGrowthData && portfolioGrowthData.length > 0 && (
              <Line options={portfolioGrowthChartOptions} data={portfolioGrowthChartData} />
            )}
            {!isLoadingPortfolioGrowth && !errorPortfolioGrowth && (!portfolioGrowthData || portfolioGrowthData.length === 0) && (
              <p className="text-center text-gray-500">No portfolio growth data available. Upload transactions first.</p>
            )}
          </div>
        </section>

        <section className="bg-gray-900 p-4 rounded-lg shadow-[0_0_15px_rgba(255,69,0,0.5)] border border-[#ff4500]">
          <h2 className="text-xl text-[#ff4500] mb-4 text-center">Portfolio Drawdown</h2>
          <div className="relative h-72 md:h-96">
            {isLoadingDrawdown && <p className="text-center text-lg animate-pulse">Loading Drawdown Data...</p>}
            {errorDrawdown && <p className="text-center text-red-500">Error: {errorDrawdown}</p>}
            {!isLoadingDrawdown && !errorDrawdown && drawdownData && drawdownData.length > 0 && (
              <Line options={drawdownChartOptions} data={drawdownChartData} />
            )}
            {!isLoadingDrawdown && !errorDrawdown && (!drawdownData || drawdownData.length === 0) && (
              <p className="text-center text-gray-500">No drawdown data available. Upload transactions first.</p>
            )}
          </div>
        </section>

        <section className="bg-gray-900 p-4 rounded-lg shadow-[0_0_15px_rgba(255,255,0,0.5)] border border-[#ffff00]">
          <h2 className="text-xl text-[#ffff00] mb-4 text-center">Asset Allocation</h2>
          <div className="relative h-72 md:h-96 flex justify-center items-center">
            {loadingComposition && <p className="text-center text-lg animate-pulse">Loading Allocation Data...</p>}
            {!loadingComposition && portfolioComposition && portfolioComposition.length > 0 && (
              <Pie options={assetAllocationChartOptions} data={assetAllocationChartData} />
            )}
            {!loadingComposition && (!portfolioComposition || portfolioComposition.length === 0) && (
              <p className="text-center text-gray-500">No allocation data available. Configure portfolio first.</p>
            )}
          </div>
        </section>

        <section className="bg-gray-900 p-4 rounded-lg shadow-[0_0_15px_rgba(0,255,204,0.5)] border border-[#00ffcc]">
          <h2 className="text-xl text-[#00ffcc] mb-4 text-center">Annual Returns Analysis</h2>
          <div className="relative h-72 md:h-96">
            {isLoadingAnnualReturns && <p className="text-center animate-pulse">Loading Annual Returns...</p>}
            {errorAnnualReturns && <p className="text-center text-red-500">Error: {errorAnnualReturns}</p>}
            {!isLoadingAnnualReturns && !errorAnnualReturns && annualReturnsData && annualReturnsData.length > 0 && (
              <Bar options={annualReturnsChartOptions} data={annualReturnsChartData} />
            )}
            {!isLoadingAnnualReturns && !errorAnnualReturns && (!annualReturnsData || annualReturnsData.length === 0) && (
              <p className="text-center text-gray-500">No annual return data available.</p>
            )}
          </div>
        </section>

        <section className="bg-gray-900 p-4 rounded-lg shadow-[0_0_15px_rgba(255,165,0,0.5)] border border-[#ffa500]">
          <h2 className="text-xl text-[#ffa500] mb-4 text-center">Monthly Returns Analysis</h2>
          <div className="relative h-72 md:h-96">
            {isLoadingMonthlyReturns && <p className="text-center animate-pulse">Loading Monthly Returns...</p>}
            {errorMonthlyReturns && <p className="text-center text-red-500">Error: {errorMonthlyReturns}</p>}
            {!isLoadingMonthlyReturns && !errorMonthlyReturns && monthlyReturnsData && monthlyReturnsData.length > 0 && (
              <Line options={monthlyReturnsChartOptions} data={monthlyReturnsChartData} />
            )}
            {!isLoadingMonthlyReturns && !errorMonthlyReturns && (!monthlyReturnsData || monthlyReturnsData.length === 0) && (
              <p className="text-center text-gray-500">No monthly return data available.</p>
            )}
          </div>
        </section>

        <section className="bg-gray-900 p-4 rounded-lg shadow-[0_0_15px_rgba(0,255,255,0.5)] border border-[#00ffff]">
          <h2 className="text-xl text-[#00ffff] mb-4 text-center">Risk & Return Metrics</h2>
          <div className="relative h-72 md:h-96 overflow-auto text-xs p-2">
            {loadingRiskReturn && <p className="text-center animate-pulse">Loading Risk/Return Metrics...</p>}
            {!loadingRiskReturn && riskReturnMetrics && (
              <pre>{JSON.stringify(riskReturnMetrics, null, 2)}</pre>
            )}
            {!loadingRiskReturn && !riskReturnMetrics && (
              <p className="text-center text-gray-500">No risk/return metrics available.</p>
            )}
          </div>
        </section>

        <section className="bg-gray-900 p-4 rounded-lg shadow-[0_0_15px_rgba(0,255,0,0.5)] border border-[#00ff00]">
          <h2 className="text-xl text-[#00ff00] mb-4 text-center">Style Analysis</h2>
          <div className="relative h-72 md:h-96 overflow-auto text-xs p-2">
            {loadingStyleAnalysis && <p className="text-center animate-pulse">Loading Style Analysis...</p>}
            {!loadingStyleAnalysis && styleAnalysis && styleAnalysis.styleAnalysis?.length > 0 && (
              <pre>{JSON.stringify(styleAnalysis, null, 2)}</pre>
            )}
            {!loadingStyleAnalysis && (!styleAnalysis || !styleAnalysis.styleAnalysis || styleAnalysis.styleAnalysis.length === 0) && (
              <p className="text-center text-gray-500">No style analysis data available.</p>
            )}
          </div>
        </section>

        <section className="bg-gray-900 p-4 rounded-lg shadow-[0_0_15px_rgba(255,0,255,0.5)] border border-[#ff00ff]">
          <h2 className="text-xl text-[#ff00ff] mb-4 text-center">Active Return Contribution</h2>
          <div className="relative h-72 md:h-96 overflow-auto text-xs p-2">
            {loadingActiveReturns && <p className="text-center animate-pulse">Loading Active Returns...</p>}
            {!loadingActiveReturns && activeReturns && activeReturns.activeReturns?.length > 0 && (
              <pre>{JSON.stringify(activeReturns, null, 2)}</pre>
            )}
            {!loadingActiveReturns && (!activeReturns || !activeReturns.activeReturns || activeReturns.activeReturns.length === 0) && (
              <p className="text-center text-gray-500">No active return data available.</p>
            )}
          </div>
        </section>

        <section className="bg-gray-900 p-4 rounded-lg shadow-[0_0_15px_rgba(0,255,204,0.5)] border border-[#00ffcc]">
          <h2 className="text-xl text-[#00ffcc] mb-4 text-center">Market Performance (Up/Down)</h2>
          <div className="relative h-72 md:h-96 overflow-auto text-xs p-2">
            {loadingMarketPerformance && <p className="text-center animate-pulse">Loading Market Performance...</p>}
            {!loadingMarketPerformance && marketPerformance && marketPerformance.marketPerformance?.length > 0 && (
              <pre>{JSON.stringify(marketPerformance, null, 2)}</pre>
            )}
            {!loadingMarketPerformance && (!marketPerformance || !marketPerformance.marketPerformance || marketPerformance.marketPerformance.length === 0) && (
              <p className="text-center text-gray-500">No market performance data available.</p>
            )}
          </div>
        </section>

        <section className="bg-gray-900 p-4 rounded-lg shadow-[0_0_15px_rgba(255,255,0,0.5)] border border-[#ffff00] lg:col-span-2">
          <h2 className="text-xl text-[#ffff00] mb-2 text-center">Fundamentals Data Date</h2>
          <div className="relative text-center p-2">
            {loadingFundamentalsDate && <p className="animate-pulse">Loading Date...</p>}
            {!loadingFundamentalsDate && fundamentalsDate && (
              <p>Data as of: <span className="font-bold">{fundamentalsDate}</span></p>
            )}
            {!loadingFundamentalsDate && !fundamentalsDate && (
              <p className="text-gray-500">Fundamentals date not available.</p>
            )}
          </div>
        </section>

      </main>

      <footer className="mt-12 text-center text-sm text-gray-500">
        Data sources: User-uploaded CSV, Alpha Vantage (via backend cache). All values approximate.
      </footer>
    </div>
  );
}

export default App;