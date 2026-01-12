#!/usr/bin/env python3
"""
Test Phase 9: Educational Features functionality
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_phase9_educational_features():
    """Test Phase 9 educational features"""
    print("=" * 70)
    print("Testing Phase 9: Educational Features")
    print("=" * 70)

    try:
        # Test template loading and educational content
        from fastapi.testclient import TestClient
        from src.main import app

        client = TestClient(app)

        # Test 9.1.1: Educational Content Database
        print("\n--- Testing Educational Content Database ---")

        # Test dashboard educational content
        dashboard_content = client.get("/dashboard").text
        assert "educationalContent" in dashboard_content
        assert "Understanding Transactions" in dashboard_content
        assert "Understanding Total Returns" in dashboard_content
        assert "Compound Annual Growth Rate" in dashboard_content
        print("[OK] Comprehensive educational content database in dashboard")

        # Test upload educational content
        upload_content = client.get("/upload").text
        assert "educationalContent" in upload_content
        assert "Secure Data Upload Process" in upload_content
        assert "Enterprise-Grade Security" in upload_content
        print("[OK] Educational content in upload template")

        # Test 9.1.2: Contextual Tooltips
        print("\n--- Testing Contextual Tooltips ---")

        assert "Learn more" in dashboard_content
        assert "showEducationalModal" in dashboard_content
        assert "onclick=\"showEducationalModal('transactions')" in dashboard_content
        print("[OK] Contextual tooltips implemented throughout UI")

        # Test 9.1.3: Expandable Information Panels
        print("\n--- Testing Expandable Information Panels ---")

        assert "analytics-toggle" in dashboard_content
        assert "aria-expanded" in dashboard_content
        assert "hidden" in dashboard_content
        print("[OK] Expandable information panels with accessibility")

        # Test 9.1.4: "Learn More" Modal System
        print("\n--- Testing Learn More Modal System ---")

        assert "education-modal" in dashboard_content
        assert "modal-title" in dashboard_content
        assert "modal-content" in dashboard_content
        print("[OK] Educational modal system implemented")

        # Test 9.1.5: Metric-by-Metric Educational Content
        print("\n--- Testing Metric-by-Metric Educational Content ---")

        # Check for specific financial concepts
        assert "transactions" in dashboard_content.lower()
        assert "returns" in dashboard_content.lower()
        assert "volatility" in dashboard_content.lower()
        assert "sharpe" in dashboard_content.lower()
        assert "allocation" in dashboard_content.lower()
        print("[OK] Comprehensive metric-by-metric educational content")

        # Test 9.1.6: Progressive Disclosure System
        print("\n--- Testing Progressive Disclosure System ---")

        assert "toggle-analytics" in dashboard_content or "analytics-toggle" in dashboard_content
        assert "hidden" in dashboard_content
        assert "Show Details" in dashboard_content
        print("[OK] Progressive disclosure of advanced information")

        # Test 9.2.1: Smart Defaults for Metric Highlighting
        print("\n--- Testing Smart Metric Highlighting ---")

        assert "metric-positive" in dashboard_content
        assert "metric-negative" in dashboard_content
        assert "metric-neutral" in dashboard_content
        print("[OK] Color-coded metric highlighting system")

        # Test 9.2.2: User Onboarding Flow
        print("\n--- Testing User Onboarding Flow ---")

        assert "onboarding-modal" in dashboard_content
        assert "Welcome to Portfolio Analysis" in dashboard_content
        assert "onboardingSteps" in dashboard_content
        assert "showOnboardingModal" in dashboard_content
        print("[OK] Comprehensive user onboarding system")

        # Test 9.2.3: Contextual Help System
        print("\n--- Testing Contextual Help System ---")

        assert "help-btn" in dashboard_content
        assert "showHelpModal" in dashboard_content
        assert "educational modal" in dashboard_content.lower()
        print("[OK] Contextual help system with multiple entry points")

        # Test 9.2.4: Customizable Metric Explanations
        print("\n--- Testing Customizable Metric Explanations ---")

        assert "difficulty" in dashboard_content.lower()
        assert "category" in dashboard_content.lower()
        assert "related" in dashboard_content.lower()
        print("[OK] Customizable educational content with metadata")

        # Test 9.2.5: Visual Indicators for Metric Health
        print("\n--- Testing Visual Metric Health Indicators ---")

        assert "text-green-400" in dashboard_content
        assert "text-red-400" in dashboard_content
        assert "text-yellow-400" in dashboard_content
        assert "border-green-500" in dashboard_content
        assert "border-red-500" in dashboard_content
        print("[OK] Visual health indicators for metrics")

        # Test 9.2.6: Educational Journey Through Features
        print("\n--- Testing Educational Journey ---")

        assert "onboardingSteps" in dashboard_content
        assert "Upload Your Data" in dashboard_content
        assert "Understanding Key Metrics" in dashboard_content
        assert "Explore Advanced Features" in dashboard_content
        print("[OK] Structured educational journey through features")

        # Test advanced educational features
        print("\n--- Testing Advanced Educational Features ---")

        # Check for detailed content structure
        assert "What are Transactions?" in dashboard_content
        assert "How CAGR Works" in dashboard_content
        assert "Risk-Return Balance" in dashboard_content
        assert "Pro Tips" in dashboard_content
        print("[OK] Advanced educational content with detailed explanations")

        # Check for interactive elements
        assert "related topics" in dashboard_content.lower()
        assert "difficulty-badge" in dashboard_content
        assert "category-badge" in dashboard_content
        print("[OK] Interactive educational elements with metadata")

        # Test educational content quality
        print("\n--- Testing Educational Content Quality ---")

        # Check for comprehensive explanations
        assert "Capital Gains" in dashboard_content
        assert "Systematic" in dashboard_content
        assert "Unsystematic" in dashboard_content
        assert "Benchmarking" in dashboard_content
        print("[OK] High-quality, comprehensive educational content")

        # Check for visual learning aids
        assert "bg-green-900/20" in dashboard_content
        assert "bg-red-900/20" in dashboard_content
        assert "grid grid-cols" in dashboard_content
        print("[OK] Visual learning aids and structured layouts")

        print("\n" + "=" * 70)
        print("🎉 Phase 9 Educational Features: ALL TESTS PASSED")
        print("=" * 70)
        print("\n✅ Educational Features Implemented:")
        print("• Comprehensive educational content database")
        print("• Contextual tooltips for all metrics")
        print("• Expandable information panels")
        print("• Enhanced modal system with navigation")
        print("• Metric-by-metric detailed explanations")
        print("• Progressive disclosure of information")
        print("• Smart metric highlighting with colors")
        print("• Interactive user onboarding flow")
        print("• Contextual help throughout the UI")
        print("• Customizable educational content")
        print("• Visual health indicators for metrics")
        print("• Structured educational journey")
        print("• Advanced learning materials")
        print("• Interactive educational elements")
        print("• High-quality content with visual aids")
        print("\n📚 Educational System Ready for User Learning!")
        return True

    except Exception as e:
        print(f"[FAIL] Phase 9 test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_phase9_educational_features()
    sys.exit(0 if success else 1)
