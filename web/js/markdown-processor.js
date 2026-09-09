// Markdown Processor for Live Interview
// Handles comprehensive markdown parsing while preserving code blocks

export class MarkdownProcessor {
    constructor(config = {}) {
        this.config = {
            preserveCodeBlocks: true,
            enableNestedLists: true,
            customBullets: true,
            professionalStyling: true,
            maxNestingLevel: 4,
            enableTables: true,
            enableBlockquotes: true,
            enableLinks: true,
            enableTaskLists: true,
            ...config
        };
        
        // Regex patterns for markdown elements
        // Regex patterns for markdown elements
        this.patterns = {
            // Code blocks (highest priority - must be preserved, supports c++, c#, etc.)
            codeBlock: /(?:```|~~~)([a-zA-Z0-9_+#.-]+)?[^\S\r\n]*\r?\n([\s\S]*?)\r?\n?[^\S\r\n]*(?:```|~~~)/g,
            
            // Display math ($$...$$)
            displayMath: /\$\$([\s\S]+?)\$\$/g,

            // Inline math ($...$, e.g. $O(N)$, $O(1)$, $n$)
            inlineMath: /(^|[^\\])\$([a-zA-Z0-9_\\{}[\]^+\-*\/=<>(),. ]+?)\$/g,

            // Headers
            header: /^(#{1,6})\s+(.+)$/m,
            
            // Tables - detect table rows (no /g flag to avoid lastIndex state bugs)
            tableRow: /^\|(.+)\|$/m,
            tableSeparator: /^\|[\s]*:?-+:?[\s]*(\|[\s]*:?-+:?[\s]*)*\|$/m,
            
            // Lists
            bulletList: /^(\s*)([-*+])\s+(.+)$/m,
            numberedList: /^(\s*)(\d+\.)\s+(.+)$/m,
            taskList: /^(\s*)([-*+])\s+\[([ xX])\]\s+(.+)$/m,
            
            // Blockquotes
            blockquote: /^>\s*(.+)$/m,
            
            // Horizontal rules (no /g flag to avoid lastIndex state bugs)
            horizontalRule: /^(\*{3,}|-{3,}|_{3,})$/m,
            
            // Inline formatting
            bold: /\*\*([^*]+)\*\*|__([^_]+)__/g,
            italic: /(?:^|[^*])\*([^*]+)\*(?!\*)|(?:^|[^_])_([^_]+)_(?!_)/g,
            strikethrough: /~~(.*?)~~/g,
            inlineCode: /`([^`\r\n]+)`/g,
            links: /\[([^\]]+)\]\(([^)]+)\)/g,
            images: /!\[([^\]]*)\]\(([^)]+)\)/g,
            
            // Line breaks and paragraphs
            doubleLineBreak: /\n\s*\n/g,
            singleLineBreak: /\n/g
        };
        
        // Counter for unique IDs
        this.elementCounter = 0;
    }

    /**
     * Main parsing method - processes raw text into structured content
     * @param {string} text - Raw text content
     * @returns {Array} - Array of content segments for streaming
     */
    parseContent(text) {
        if (!text || typeof text !== 'string') {
            return [{ type: 'text', content: '', html: '' }];
        }

        // Step 1: Extract and protect code blocks
        const { textWithPlaceholders, codeBlocks } = this.extractCodeBlocks(text);
        
        // Step 1b: Neutralize raw HTML in the remaining source BEFORE any markdown
        // substitution. Fenced code blocks were already pulled out above, so their
        // content is untouched here and stays escaped exactly once at render time.
        const escapedText = this.escapeMarkdownSource(textWithPlaceholders);

        // Step 2: Parse block elements (headers, lists, paragraphs, tables, etc.)
        const blockParsed = this.parseBlockElements(escapedText);
        
        // Step 3: Parse inline elements within each block
        const inlineParsed = this.parseInlineElements(blockParsed);
        
        // Step 4: Restore code blocks
        const finalContent = this.restoreCodeBlocks(inlineParsed, codeBlocks);
        
        return finalContent;
    }

    /**
     * Extract code blocks and replace with placeholders
     */
    extractCodeBlocks(text) {
        const codeBlocks = [];
        
        // Reset regex to avoid issues with global flag
        this.patterns.codeBlock.lastIndex = 0;
        
        let textWithPlaceholders = text.replace(this.patterns.codeBlock, (match, language, code) => {
            const id = `__CODE_BLOCK_${codeBlocks.length}__`;
            codeBlocks.push({
                id,
                type: 'code',
                language: (language || 'javascript').trim(),
                content: code.replace(/^\r?\n/, '').replace(/\r?\n$/, ''),
                originalMatch: match
            });
            return `\n\n${id}\n\n`;
        });
        
        // Handle edge case: unclosed code block at end of text (e.g. streaming or truncated output)
        const unclosedFenceMatch = textWithPlaceholders.match(/(?:^|\n)[^\S\r\n]*(?:```|~~~)([a-zA-Z0-9_+#.-]+)?[^\S\r\n]*\r?\n([\s\S]*)$/);
        if (unclosedFenceMatch) {
            const fullMatch = unclosedFenceMatch[0];
            const language = unclosedFenceMatch[1];
            const code = unclosedFenceMatch[2];
            const id = `__CODE_BLOCK_${codeBlocks.length}__`;
            codeBlocks.push({
                id,
                type: 'code',
                language: (language || 'javascript').trim(),
                content: code.replace(/^\r?\n/, '').replace(/\r?\n$/, ''),
                originalMatch: fullMatch
            });
            textWithPlaceholders = textWithPlaceholders.substring(0, textWithPlaceholders.length - fullMatch.length) + `\n\n${id}\n\n`;
        }

        return { textWithPlaceholders, codeBlocks };
    }

    /**
     * Parse block-level elements (headers, lists, paragraphs, tables, etc.)
     */
    parseBlockElements(text) {
        const lines = text.split('\n');
        const blocks = [];
        let currentBlock = null;
        let currentList = null;
        let currentTable = null;
        let currentBlockquote = null;
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const trimmedLine = line.trim();
            
            // Skip empty lines between blocks
            if (!trimmedLine) {
                this.endCurrentBlocks(blocks, { currentBlock, currentList, currentTable, currentBlockquote });
                currentBlock = currentList = currentTable = currentBlockquote = null;
                continue;
            }

            // Check for code block placeholders (keep as distinct block)
            const codeBlockMatch = trimmedLine.match(/^(__CODE_BLOCK_\d+__)$/);
            if (codeBlockMatch) {
                this.endCurrentBlocks(blocks, { currentBlock, currentList, currentTable, currentBlockquote });
                currentBlock = currentList = currentTable = currentBlockquote = null;
                
                blocks.push({
                    type: 'code_placeholder',
                    id: codeBlockMatch[1]
                });
                continue;
            }
            
            // Check for horizontal rules
            if (this.patterns.horizontalRule.test(trimmedLine)) {
                this.endCurrentBlocks(blocks, { currentBlock, currentList, currentTable, currentBlockquote });
                currentBlock = currentList = currentTable = currentBlockquote = null;
                
                blocks.push({
                    type: 'horizontalRule',
                    id: `hr-${this.elementCounter++}`
                });
                continue;
            }
            
            // Check for headers
            const headerMatch = trimmedLine.match(/^(#{1,6})\s+(.+)$/);
            if (headerMatch) {
                this.endCurrentBlocks(blocks, { currentBlock, currentList, currentTable, currentBlockquote });
                currentBlock = currentList = currentTable = currentBlockquote = null;
                
                blocks.push({
                    type: 'header',
                    level: headerMatch[1].length,
                    content: headerMatch[2].trim(),
                    id: `header-${this.elementCounter++}`
                });
                continue;
            }
            
            // Check for table rows
            if (trimmedLine.startsWith('|') && trimmedLine.endsWith('|')) {
                if (currentBlock || currentList || currentBlockquote) {
                    this.endCurrentBlocks(blocks, { currentBlock, currentList, currentBlockquote });
                    currentBlock = currentList = currentBlockquote = null;
                }
                
                // Check if this is a table separator
                const isSeparator = this.patterns.tableSeparator.test(trimmedLine);
                
                if (!currentTable) {
                    currentTable = {
                        type: 'table',
                        headers: [],
                        rows: [],
                        alignments: [],
                        id: `table-${this.elementCounter++}`
                    };
                }
                
                if (isSeparator) {
                    // Parse alignment from separator
                    const cells = trimmedLine.split('|').slice(1, -1);
                    currentTable.alignments = cells.map(cell => {
                        const trimmed = cell.trim();
                        if (trimmed.startsWith(':') && trimmed.endsWith(':')) return 'center';
                        if (trimmed.endsWith(':')) return 'right';
                        return 'left';
                    });
                } else {
                    // Parse table row
                    const cells = trimmedLine.split('|').slice(1, -1).map(cell => cell.trim());
                    
                    if (currentTable.headers.length === 0 && currentTable.rows.length === 0) {
                        currentTable.headers = cells;
                    } else {
                        currentTable.rows.push(cells);
                    }
                }
                continue;
            } else if (currentTable) {
                // End table if we hit a non-table line
                blocks.push(currentTable);
                currentTable = null;
            }
            
            // Check for blockquotes
            const blockquoteMatch = trimmedLine.match(/^>\s*(.+)$/);
            if (blockquoteMatch) {
                if (currentBlock || currentList || currentTable) {
                    this.endCurrentBlocks(blocks, { currentBlock, currentList, currentTable });
                    currentBlock = currentList = currentTable = null;
                }
                
                if (!currentBlockquote) {
                    currentBlockquote = {
                        type: 'blockquote',
                        content: blockquoteMatch[1],
                        id: `blockquote-${this.elementCounter++}`
                    };
                } else {
                    currentBlockquote.content += ' ' + blockquoteMatch[1];
                }
                continue;
            } else if (currentBlockquote) {
                blocks.push(currentBlockquote);
                currentBlockquote = null;
            }
            
            // Check for task lists
            const taskMatch = line.match(/^(\s*)([-*+])\s+\[([ xX])\]\s+(.+)$/);
            if (taskMatch) {
                const indent = taskMatch[1].length;
                const checked = taskMatch[3].toLowerCase() === 'x';
                const content = taskMatch[4];
                
                if (currentBlock || currentTable || currentBlockquote) {
                    this.endCurrentBlocks(blocks, { currentBlock, currentTable, currentBlockquote });
                    currentBlock = currentTable = currentBlockquote = null;
                }
                
                if (!currentList || currentList.listType !== 'task') {
                    if (currentList) blocks.push(currentList);
                    currentList = {
                        type: 'list',
                        listType: 'task',
                        items: [],
                        id: `list-${this.elementCounter++}`
                    };
                }
                
                currentList.items.push({
                    content: content,
                    checked: checked,
                    indent: Math.floor(indent / 2),
                    id: `item-${this.elementCounter++}`
                });
                continue;
            }
            
            // Check for bullet lists
            const bulletMatch = line.match(/^(\s*)([-*+])\s+(.+)$/);
            if (bulletMatch) {
                const indent = bulletMatch[1].length;
                const content = bulletMatch[3];
                
                if (currentBlock || currentTable || currentBlockquote) {
                    this.endCurrentBlocks(blocks, { currentBlock, currentTable, currentBlockquote });
                    currentBlock = currentTable = currentBlockquote = null;
                }
                
                if (!currentList || currentList.listType !== 'bullet') {
                    if (currentList) blocks.push(currentList);
                    currentList = {
                        type: 'list',
                        listType: 'bullet',
                        items: [],
                        id: `list-${this.elementCounter++}`
                    };
                }
                
                currentList.items.push({
                    content: content,
                    indent: Math.floor(indent / 2),
                    id: `item-${this.elementCounter++}`
                });
                continue;
            }
            
            // Check for numbered lists
            const numberedMatch = line.match(/^(\s*)(\d+\.)\s+(.+)$/);
            if (numberedMatch) {
                const indent = numberedMatch[1].length;
                const content = numberedMatch[3];
                
                if (currentBlock || currentTable || currentBlockquote) {
                    this.endCurrentBlocks(blocks, { currentBlock, currentTable, currentBlockquote });
                    currentBlock = currentTable = currentBlockquote = null;
                }
                
                if (!currentList || currentList.listType !== 'numbered') {
                    if (currentList) blocks.push(currentList);
                    currentList = {
                        type: 'list',
                        listType: 'numbered',
                        items: [],
                        id: `list-${this.elementCounter++}`
                    };
                }
                
                currentList.items.push({
                    content: content,
                    indent: Math.floor(indent / 2),
                    id: `item-${this.elementCounter++}`
                });
                continue;
            }
            
            // Regular text - add to current paragraph or create new one
            if (currentList || currentTable || currentBlockquote) {
                this.endCurrentBlocks(blocks, { currentList, currentTable, currentBlockquote });
                currentList = currentTable = currentBlockquote = null;
            }
            
            if (!currentBlock || currentBlock.type !== 'paragraph') {
                currentBlock = {
                    type: 'paragraph',
                    content: trimmedLine,
                    id: `paragraph-${this.elementCounter++}`
                };
            } else {
                currentBlock.content += ' ' + trimmedLine;
            }
        }
        
        // Add remaining blocks
        this.endCurrentBlocks(blocks, { currentBlock, currentList, currentTable, currentBlockquote });
        
        return blocks;
    }

    /**
     * Helper method to end current blocks and add them to the blocks array
     */
    endCurrentBlocks(blocks, { currentBlock, currentList, currentTable, currentBlockquote }) {
        if (currentBlock) blocks.push(currentBlock);
        if (currentList) blocks.push(currentList);
        if (currentTable) blocks.push(currentTable);
        if (currentBlockquote) blocks.push(currentBlockquote);
    }

    /**
     * Parse inline elements (bold, italic, code, links, etc.)
     */
    parseInlineElements(blocks) {
        return blocks.map(block => {
            if (block.type === 'list') {
                // Process each list item
                block.items = block.items.map(item => ({
                    ...item,
                    content: this.processInlineFormatting(item.content)
                }));
            } else if (block.type === 'table') {
                // Process table headers and cells
                block.headers = block.headers.map(header => this.processInlineFormatting(header));
                block.rows = block.rows.map(row => 
                    row.map(cell => this.processInlineFormatting(cell))
                );
            } else if (block.content) {
                block.content = this.processInlineFormatting(block.content);
            }
            return block;
        });
    }

    /**
     * Process inline formatting for a text string
     */
    processInlineFormatting(text) {
        if (!text) return text;
        
        // Process in order of precedence
        // 1. Images (before links)
        text = text.replace(this.patterns.images, (match, alt, src) => {
            return `<img class="markdown-image" src="${src}" alt="${alt}" />`;
        });
        
        // 2. Links
        text = text.replace(this.patterns.links, (match, linkText, url) => {
            return `<a class="markdown-link" href="${url}" target="_blank" rel="noopener noreferrer">${linkText}</a>`;
        });
        
        // 3. Inline code (highest priority for text formatting - don't format inside)
        const codeSegments = [];
        let processedText = text.replace(this.patterns.inlineCode, (match, code) => {
            const id = `__INLINE_CODE_${codeSegments.length}__`;
            codeSegments.push({
                id,
                content: code,
                html: `<code class="inline-code">${code}</code>`
            });
            return id;
        });
        
        // 4. Inline math (e.g. $O(N)$, $O(1)$, $n$)
        processedText = processedText.replace(this.patterns.inlineMath, (match, prefix, mathContent) => {
            return `${prefix}<span class="inline-math"><code class="math-code">${mathContent.trim()}</code></span>`;
        });

        // 5. Bold text
        processedText = processedText.replace(/\*\*([^*]+)\*\*/g, '<strong class="markdown-bold">$1</strong>');
        processedText = processedText.replace(/__([^_]+)__/g, '<strong class="markdown-bold">$1</strong>');
        
        // 6. Italic text
        processedText = processedText.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, '$1<em class="markdown-italic">$2</em>');
        processedText = processedText.replace(/(^|[^_])_([^_]+)_(?!_)/g, '$1<em class="markdown-italic">$2</em>');
        
        // 7. Strikethrough
        processedText = processedText.replace(this.patterns.strikethrough, (match, content) => {
            return `<del class="markdown-strikethrough">${content}</del>`;
        });
        
        // 8. Restore inline code
        codeSegments.forEach(segment => {
            processedText = processedText.replace(segment.id, () => segment.html);
        });
        
        return processedText;
    }

    /**
     * Restore code blocks in final content
     */
    restoreCodeBlocks(blocks, codeBlocks) {
        const codeBlockMap = {};
        codeBlocks.forEach(block => {
            codeBlockMap[block.id] = block;
        });
        
        const finalBlocks = [];
        
        blocks.forEach(block => {
            if (block.type === 'code_placeholder') {
                const codeBlock = codeBlockMap[block.id];
                if (codeBlock) {
                    finalBlocks.push(codeBlock);
                }
            } else if (block.type === 'paragraph' && block.content && block.content.includes('__CODE_BLOCK_')) {
                // Split paragraph by code block placeholders
                const parts = block.content.split(/(__CODE_BLOCK_\d+__)/);
                
                parts.forEach(part => {
                    if (part.match(/^__CODE_BLOCK_\d+__$/)) {
                        const codeBlock = codeBlockMap[part];
                        if (codeBlock) {
                            finalBlocks.push(codeBlock);
                        }
                    } else if (part.trim()) {
                        finalBlocks.push({
                            type: 'paragraph',
                            content: part.trim(),
                            id: `paragraph-${this.elementCounter++}`
                        });
                    }
                });
            } else if (block.type === 'table' && block.headers) {
                // Process table headers and cells for code blocks
                const processedHeaders = block.headers.map(header => {
                    if (header && header.includes('__CODE_BLOCK_')) {
                        // For table cells, we'll inline the code
                        return header.replace(/(__CODE_BLOCK_\d+__)/g, (match) => {
                            const codeBlock = codeBlockMap[match];
                            return codeBlock ? `<code>${this.escapeHtml(codeBlock.content)}</code>` : match;
                        });
                    }
                    return header;
                });
                
                const processedRows = block.rows.map(row => 
                    row.map(cell => {
                        if (cell && cell.includes('__CODE_BLOCK_')) {
                            return cell.replace(/(__CODE_BLOCK_\d+__)/g, (match) => {
                                const codeBlock = codeBlockMap[match];
                                return codeBlock ? `<code>${this.escapeHtml(codeBlock.content)}</code>` : match;
                            });
                        }
                        return cell;
                    })
                );
                
                finalBlocks.push({
                    ...block,
                    headers: processedHeaders,
                    rows: processedRows
                });
            } else if (block.content && block.content.includes('__CODE_BLOCK_')) {
                // Process other block types that might contain code blocks
                const processedContent = block.content.replace(/(__CODE_BLOCK_\d+__)/g, (match) => {
                    const codeBlock = codeBlockMap[match];
                    return codeBlock ? `<code>${this.escapeHtml(codeBlock.content)}</code>` : match;
                });
                
                finalBlocks.push({
                    ...block,
                    content: processedContent
                });
            } else {
                finalBlocks.push(block);
            }
        });
        
        return finalBlocks;
    }

    /**
     * Generate HTML for a content block
     */
    generateHTML(block) {
        switch (block.type) {
            case 'header':
                return this.generateHeaderHTML(block);
            case 'list':
                return this.generateListHTML(block);
            case 'paragraph':
                return this.generateParagraphHTML(block);
            case 'code':
                return this.generateCodeHTML(block);
            case 'table':
                return this.generateTableHTML(block);
            case 'blockquote':
                return this.generateBlockquoteHTML(block);
            case 'horizontalRule':
                return this.generateHorizontalRuleHTML(block);
            default:
                return `<div class="unknown-block">${this.escapeHtml(block.content || '')}</div>`;
        }
    }

    generateHeaderHTML(block) {
        const level = Math.min(Math.max(block.level, 1), 6);
        const className = `markdown-header markdown-h${level}`;
        return `<h${level} class="${className}" id="${block.id}">${block.content}</h${level}>`;
    }

    generateListHTML(block) {
        if (block.listType === 'task') {
            return this.generateTaskListHTML(block);
        }
        
        const tag = block.listType === 'numbered' ? 'ol' : 'ul';
        const className = `markdown-list markdown-${block.listType}-list`;
        
        let html = `<${tag} class="${className}">`;
        
        block.items.forEach(item => {
            const indentClass = item.indent > 0 ? ` indent-${Math.min(item.indent, this.config.maxNestingLevel)}` : '';
            html += `<li class="markdown-list-item${indentClass}">${item.content}</li>`;
        });
        
        html += `</${tag}>`;
        return html;
    }

    generateTaskListHTML(block) {
        const className = 'markdown-list markdown-task-list';
        
        let html = `<ul class="${className}">`;
        
        block.items.forEach(item => {
            const indentClass = item.indent > 0 ? ` indent-${Math.min(item.indent, this.config.maxNestingLevel)}` : '';
            const checkedAttr = item.checked ? ' checked' : '';
            const checkedClass = item.checked ? ' task-checked' : ' task-unchecked';
            
            html += `<li class="markdown-task-item${indentClass}${checkedClass}">`;
            html += `<input type="checkbox" class="task-checkbox" disabled${checkedAttr}>`;
            html += `<span class="task-content">${item.content}</span>`;
            html += `</li>`;
        });
        
        html += `</ul>`;
        return html;
    }

    generateTableHTML(block) {
        if (!block.headers || block.headers.length === 0) {
            return '';
        }
        
        const className = 'markdown-table';
        let html = `<div class="table-wrapper"><table class="${className}">`;
        
        // Generate table header
        html += '<thead><tr>';
        block.headers.forEach((header, index) => {
            const alignment = block.alignments[index] || 'left';
            const alignClass = alignment !== 'left' ? ` text-${alignment}` : '';
            html += `<th class="table-header${alignClass}">${header}</th>`;
        });
        html += '</tr></thead>';
        
        // Generate table body
        if (block.rows && block.rows.length > 0) {
            html += '<tbody>';
            block.rows.forEach(row => {
                html += '<tr>';
                row.forEach((cell, index) => {
                    const alignment = block.alignments[index] || 'left';
                    const alignClass = alignment !== 'left' ? ` text-${alignment}` : '';
                    html += `<td class="table-cell${alignClass}">${cell}</td>`;
                });
                html += '</tr>';
            });
            html += '</tbody>';
        }
        
        html += '</table></div>';
        return html;
    }

    generateBlockquoteHTML(block) {
        const className = 'markdown-blockquote';
        return `<blockquote class="${className}">${block.content}</blockquote>`;
    }

    generateHorizontalRuleHTML(block) {
        const className = 'markdown-hr';
        return `<hr class="${className}" />`;
    }

    generateParagraphHTML(block) {
        if (!block.content || !block.content.trim()) {
            return '';
        }
        return `<p class="markdown-paragraph">${block.content}</p>`;
    }

    normalizeLanguage(lang) {
        if (!lang) return 'text';
        const l = lang.toLowerCase().trim();
        const map = {
            'c++': 'cpp',
            'c#': 'csharp',
            'cs': 'csharp',
            'f#': 'fsharp',
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'sh': 'bash',
            'shell': 'bash',
            'zsh': 'bash',
            'yml': 'yaml',
            'golang': 'go',
            'rb': 'ruby',
            'rs': 'rust',
            'md': 'markdown'
        };
        return map[l] || l;
    }

    generateCodeHTML(block) {
        const rawLang = block.language || 'text';
        const normLang = this.normalizeLanguage(rawLang);
        const escapedCode = this.escapeHtml(block.content || '');
        const blockId = block.id || `code-block-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

        return `<div class="code-block-container" data-block-id="${blockId}">` +
            `<div class="code-block-header">` +
                `<span class="code-language">${this.escapeHtml(rawLang)}</span>` +
                `<button class="copy-button" type="button" title="Copy code">📋</button>` +
            `</div>` +
            `<pre class="code-block language-${normLang}"><code class="language-${normLang}">${escapedCode}</code></pre>` +
        `</div>`;
    }

    /**
     * Escape raw HTML in markdown SOURCE text, before any markdown pattern
     * substitution runs.
     *
     * Deliberately does NOT escape '>': blockquote detection in
     * parseBlockElements matches /^>\s*(.+)$/ on this string, and a literal '>'
     * cannot open a tag once '<' is escaped. Deliberately does NOT escape "'"
     * either: every attribute emitted by this class is wrapped in double quotes
     * (which ARE escaped), and leaving "'" alone avoids injecting '$&' sequences
     * into text that later passes through String.prototype.replace.
     */
    escapeMarkdownSource(text) {
        if (!text || typeof text !== 'string') return text;
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/"/g, '&quot;');
    }

    /**
     * Utility method to escape HTML
     */
    escapeHtml(text) {
        if (!text) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /**
     * Get configuration
     */
    getConfig() {
        return { ...this.config };
    }

    /**
     * Update configuration
     */
    updateConfig(newConfig) {
        this.config = { ...this.config, ...newConfig };
    }
}