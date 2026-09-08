// Demo script to test real-time streaming markdown parsing
// This simulates chunks arriving like they would from a real streaming API

export function testStreamingMarkdown() {
    console.log('🧪 Testing Real-Time Streaming Markdown Parser...');
    
    // Test chunks that simulate real streaming scenarios
    const testChunks = [
        // Test 1: Simple paragraph
        "This is a simple ",
        "paragraph with some text.",
        
        // Test 2: Header formation
        "\n\n## Problem",
        " Analysis\n\n",
        
        // Test 3: Bold text formation
        "The **two sum**",
        " problem is a classic ",
        "**algorithm** challenge.",
        
        // Test 4: Code block formation
        "\n\n```python\n",
        "def two_sum(nums, target):\n",
        "    # Hash map approach\n",
        "    seen = {}\n",
        "    for i, num in enumerate(nums):\n",
        "        complement = target - num\n",
        "        if complement in seen:\n",
        "            return [seen[complement], i]\n",
        "        seen[num] = i\n",
        "    return []\n",
        "```",
        
        // Test 5: List formation
        "\n\n### Approach:\n",
        "1. Create a hash map\n",
        "2. Iterate through array\n",
        "3. Check for complement\n",
        "4. Return indices\n",
        
        // Test 6: Bullet list
        "\n\n**Key benefits:**\n",
        "- O(n) time complexity\n",
        "- O(n) space complexity\n",
        "- Single pass solution\n",
        
        // Test 7: Inline code and links
        "\n\nTime complexity: `O(n)` where `n` is the length of the array.\n",
        "For more details, see [LeetCode Problem](https://leetcode.com/problems/two-sum/).",
        
        // Test 8: Mixed formatting
        "\n\n*Remember:* **Always** consider the `space-time` **tradeoff** when solving problems!"
    ];
    
    // Get the streaming markdown parser from the live interview UI
    const parser = window.liveInterviewUI?.markdownParser;
    if (!parser) {
        console.error('❌ Markdown parser not found. Make sure live interview UI is initialized.');
        return;
    }
    
    // Reset parser for test
    parser.reset();
    
    // Create a test output container
    let testContainer = document.getElementById('markdown-test-output');
    if (!testContainer) {
        testContainer = document.createElement('div');
        testContainer.id = 'markdown-test-output';
        testContainer.style.cssText = `
            position: fixed;
            top: 10px;
            right: 10px;
            width: 900px;
            max-height: 900px;
            background: rgba(0, 0, 0, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            padding: 16px;
            color: white;
            font-family: inherit;
            font-size: 14px;
            overflow-y: auto;
            z-index: 10000;
            backdrop-filter: blur(10px);
        `;
        
        // Add close button
        const closeBtn = document.createElement('button');
        closeBtn.textContent = '×';
        closeBtn.style.cssText = `
            position: absolute;
            top: 8px;
            right: 8px;
            background: none;
            border: none;
            color: white;
            font-size: 18px;
            cursor: pointer;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        closeBtn.onclick = () => testContainer.remove();
        testContainer.appendChild(closeBtn);
        
        // Add title
        const title = document.createElement('h3');
        title.textContent = '🧪 Real-Time Markdown Test';
        title.style.cssText = 'margin: 0 0 12px 0; color: #64d2ff;';
        testContainer.appendChild(title);
        
        // Add content area
        const content = document.createElement('div');
        content.id = 'test-content';
        content.style.cssText = 'line-height: 1.5;';
        testContainer.appendChild(content);
        
        document.body.appendChild(testContainer);
    }
    
    const contentArea = testContainer.querySelector('#test-content');
    
    // Function to simulate streaming
    let chunkIndex = 0;
    const streamChunk = () => {
        if (chunkIndex < testChunks.length) {
            const chunk = testChunks[chunkIndex];
            console.log(`📝 Processing chunk ${chunkIndex + 1}/${testChunks.length}:`, JSON.stringify(chunk));
            
            // Process through parser
            const renderedHTML = parser.processChunk(chunk);
            
            // Update display
            contentArea.innerHTML = renderedHTML;
            
            chunkIndex++;
            
            // Continue streaming with realistic delay
            setTimeout(streamChunk, 150 + Math.random() * 200);
        } else {
            // Finalize
            console.log('✅ Streaming complete, finalizing...');
            const finalHTML = parser.finalize();
            contentArea.innerHTML = finalHTML;
            console.log('🎉 Real-time markdown test completed!');
            
            // Start auto-close countdown
            startAutoCloseCountdown(testContainer, 10);
        }
    };
    
    // Start the test
    console.log('🚀 Starting streaming markdown test...');
    setTimeout(streamChunk, 500);
}

/**
 * Test with specific sample markdown content
 */
export function testSampleMarkdown() {
    console.log('🧪 Testing with Sample Markdown Content...');
    
    // Sample markdown content broken into streaming chunks
    const sampleChunks = [
        "## 🎯 Problem Understanding\n",
        "The problem is asking for a Python solution to a LeetCode problem. However, the specific problem is not mentioned. ",
        "For the purpose of this response, I will choose a popular LeetCode problem, \"Two Sum,\" which is a common coding challenge.\n\n",
        
        "## 💡 Solution Strategy\n\n",
        "### 🚀 Approach 1: Brute Force Method\n",
        "- **Algorithm:** The brute force approach involves iterating through the list of numbers ",
        "and checking every pair to see if their sum equals the target.\n",
        "- **Time Complexity:** O(n^2) - This is because for each number, we are potentially checking every other number.\n",
        "- **Space Complexity:** O(1) - We only need a constant amount of space to store the indices of the two numbers.\n",
        "- **Why this approach:** This approach is straightforward and easy to understand but is not efficient for large lists due to its quadratic time complexity.\n\n",
        
        "```python\n",
        "def twoSum_bruteForce(nums, target):\n",
        "    for i in range(len(nums)):\n",
        "        for j in range(i + 1, len(nums)):\n",
        "            if nums[i] + nums[j] == target:\n",
        "                return [i, j]\n",
        "```\n\n",
        
        "### ⚡ Approach 2: Hash Table Method\n",
        "- **Algorithm:** We can use a hash table (dictionary in Python) to store the numbers we've seen so far and their indices. ",
        "For each number, we check if its complement (target - number) is in the hash table.\n",
        "- **Time Complexity:** O(n) - We make a single pass through the list of numbers.\n",
        "- **Space Complexity:** O(n) - In the worst case, we might store every number in the hash table.\n",
        "- **Why this is better:** This approach is much more efficient than the brute force method, especially for large lists, because it reduces the time complexity to linear.\n\n",
        
        "```python\n",
        "def twoSum_hashTable(nums, target):\n",
        "    num_dict = {}\n",
        "    for i, num in enumerate(nums):\n",
        "        complement = target - num\n",
        "        if complement in num_dict:\n",
        "            return [num_dict[complement], i]\n",
        "        num_dict[num] = i\n",
        "```\n\n",
        
        "## 🔍 Implementation Details\n",
        "- **Edge Cases:** The hash table approach handles edge cases well, such as when the list is empty or contains only one element, ",
        "because it simply returns without finding a solution in such cases.\n",
        "- **Testing Strategy:** Key test cases include lists with two numbers that sum to the target, lists with no such pair, ",
        "and edge cases like empty lists or lists with a single element.\n",
        "- **Trade-offs:** The brute force method is simpler but much less efficient for large inputs, ",
        "while the hash table method is more efficient but uses more memory.\n",
        "- **Real-world Context:** The two-sum problem is a basic example of how hash tables can be used to solve problems efficiently, ",
        "which is a common pattern in many real-world applications, such as data processing and algorithmic challenges."
    ];
    
    // Get the streaming markdown parser from the live interview UI
    const parser = window.liveInterviewUI?.markdownParser;
    if (!parser) {
        console.error('❌ Markdown parser not found. Make sure live interview UI is initialized.');
        return;
    }
    
    // Reset parser for test
    parser.reset();
    
    // Create a test output container
    let testContainer = document.getElementById('sample-markdown-test');
    if (!testContainer) {
        testContainer = document.createElement('div');
        testContainer.id = 'sample-markdown-test';
        testContainer.style.cssText = `
            position: fixed;
            top: 10px;
            left: 10px;
            width: 50%;
            max-height: 80vh;
            background: rgba(0, 0, 0, 0.95);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            padding: 16px;
            color: white;
            font-family: inherit;
            font-size: 14px;
            overflow-y: auto;
            z-index: 10000;
            backdrop-filter: blur(10px);
        `;
        
        // Add close button
        const closeBtn = document.createElement('button');
        closeBtn.textContent = '×';
        closeBtn.style.cssText = `
            position: absolute;
            top: 8px;
            right: 8px;
            background: none;
            border: none;
            color: white;
            font-size: 18px;
            cursor: pointer;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        closeBtn.onclick = () => testContainer.remove();
        testContainer.appendChild(closeBtn);
        
        // Add title
        const title = document.createElement('h3');
        title.textContent = '🧪 Sample Markdown Real-Time Test';
        title.style.cssText = 'margin: 0 0 12px 0; color: #64d2ff;';
        testContainer.appendChild(title);
        
        // Add content area
        const content = document.createElement('div');
        content.id = 'sample-test-content';
        content.style.cssText = 'line-height: 1.5;';
        testContainer.appendChild(content);
        
        document.body.appendChild(testContainer);
    }
    
    const contentArea = testContainer.querySelector('#sample-test-content');
    
    // Function to simulate streaming
    let chunkIndex = 0;
    const streamChunk = () => {
        if (chunkIndex < sampleChunks.length) {
            const chunk = sampleChunks[chunkIndex];
            console.log(`📝 Processing sample chunk ${chunkIndex + 1}/${sampleChunks.length}:`, JSON.stringify(chunk.substring(0, 50) + '...'));
            
            // Process through parser
            const renderedHTML = parser.processChunk(chunk);
            
            // Update display
            contentArea.innerHTML = renderedHTML;
            
            chunkIndex++;
            
            // Continue streaming with realistic delay
            setTimeout(streamChunk, 200 + Math.random() * 300);
        } else {
            // Finalize
            console.log('✅ Sample streaming complete, finalizing...');
            const finalHTML = parser.finalize();
            contentArea.innerHTML = finalHTML;
            console.log('🎉 Sample markdown real-time test completed!');
            
            // Start auto-close countdown
            startAutoCloseCountdown(testContainer, 10);
        }
    };
    
    // Start the test
    console.log('🚀 Starting sample markdown streaming test...');
    setTimeout(streamChunk, 500);
}

/**
 * Auto-close countdown for test windows
 */
function startAutoCloseCountdown(container, seconds) {
    let remainingSeconds = seconds;
    
    // Create countdown display
    const countdownDiv = document.createElement('div');
    countdownDiv.style.cssText = `
        position: absolute;
        bottom: 8px;
        right: 8px;
        background: rgba(0, 0, 0, 0.8);
        color: #fbbf24;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 500;
        border: 1px solid rgba(251, 191, 36, 0.3);
        backdrop-filter: blur(5px);
        z-index: 10001;
    `;
    container.appendChild(countdownDiv);
    
    // Update countdown every second
    const updateCountdown = () => {
        if (remainingSeconds > 0) {
            countdownDiv.textContent = `Auto-close in ${remainingSeconds}s`;
            remainingSeconds--;
            setTimeout(updateCountdown, 1000);
        } else {
            // Close the test window
            container.remove();
            console.log('🕒 Test window auto-closed after 10 seconds');
        }
    };
    
    // Start countdown
    updateCountdown();
    
    // Allow manual close to cancel auto-close
    const closeBtn = container.querySelector('button');
    if (closeBtn) {
        const originalOnClick = closeBtn.onclick;
        closeBtn.onclick = () => {
            remainingSeconds = 0; // Stop countdown
            if (originalOnClick) originalOnClick();
        };
    }
}

/**
 * Manually close all test windows
 */
function closeAllTestWindows() {
    const testWindows = [
        document.getElementById('markdown-test-output'),
        document.getElementById('sample-markdown-test')
    ];
    
    testWindows.forEach(window => {
        if (window) {
            window.remove();
            console.log('🗙 Test window manually closed');
        }
    });
}

/**
 * Close specific test window
 */
function closeTestWindow(testId) {
    const testWindow = document.getElementById(testId);
    if (testWindow) {
        testWindow.remove();
        console.log(`🗙 Test window '${testId}' manually closed`);
    } else {
        console.log(`⚠️ Test window '${testId}' not found`);
    }
}

// Add to window for easy testing
window.testStreamingMarkdown = testStreamingMarkdown;
window.testSampleMarkdown = testSampleMarkdown;
window.closeAllTestWindows = closeAllTestWindows;
window.closeTestWindow = closeTestWindow;

// Auto-test on load if in dev mode
if (window.isDev) {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => {
            console.log('🧪 Auto-starting markdown test in dev mode...');
            // Uncomment to auto-test: testSampleMarkdown();
        }, 2000);
    });
} 