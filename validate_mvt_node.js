#!/usr/bin/env node
/**
 * MVT (Mapbox Vector Tile) Validation Script - Node.js Version
 * Validates MVT files using @mapbox/vtvalidate library
 */

const fs = require('fs');
const path = require('path');
const vtvalidate = require('@mapbox/vtvalidate');

function validateMvtFile(filePath) {
    try {
        // Check if file exists
        if (!fs.existsSync(filePath)) {
            return {
                valid: false,
                error: `File not found: ${filePath}`
            };
        }

        // Get file stats
        const stats = fs.statSync(filePath);
        const fileSize = stats.size;

        if (fileSize === 0) {
            return {
                valid: false,
                error: 'File is empty'
            };
        }

        // Read the MVT file
        const tileData = fs.readFileSync(filePath);

        // Validate using vtvalidate
        try {
            const isValid = vtvalidate(tileData);
            
            if (!isValid) {
                return {
                    valid: false,
                    error: 'MVT validation failed - invalid tile structure',
                    fileSize: fileSize
                };
            }

            // If validation passes, try to get more details
            // Note: vtvalidate only validates structure, doesn't decode content
            return {
                valid: true,
                fileSize: fileSize,
                message: 'MVT structure is valid (basic validation)',
                note: 'For detailed content analysis, use the Python version'
            };

        } catch (error) {
            return {
                valid: false,
                error: `Validation error: ${error.message}`,
                fileSize: fileSize
            };
        }

    } catch (error) {
        return {
            valid: false,
            error: `Unexpected error: ${error.message}`
        };
    }
}

function printValidationResults(results) {
    console.log('='.repeat(60));
    console.log('MVT FILE VALIDATION RESULTS (Node.js)');
    console.log('='.repeat(60));

    if (!results.valid) {
        console.log('❌ VALIDATION FAILED');
        console.log(`Error: ${results.error}`);
        if (results.fileSize !== undefined) {
            console.log(`File size: ${results.fileSize} bytes`);
        }
        return;
    }

    console.log('✅ VALIDATION SUCCESSFUL');
    console.log(`📁 File size: ${results.fileSize.toLocaleString()} bytes`);
    console.log(`💬 ${results.message}`);
    if (results.note) {
        console.log(`📝 Note: ${results.note}`);
    }

    console.log('\n' + '='.repeat(60));
}

function main() {
    if (process.argv.length !== 3) {
        console.log('Usage: node validate_mvt_node.js <path_to_mvt_file>');
        console.log('Example: node validate_mvt_node.js "C:\\Users\\ADMIN\\Downloads\\30408.mvt"');
        process.exit(1);
    }

    const filePath = process.argv[2];
    console.log(`🔍 Validating MVT file: ${filePath}`);
    console.log();

    const results = validateMvtFile(filePath);
    printValidationResults(results);

    if (results.valid) {
        console.log('🎉 The MVT file is valid and ready to use!');
    } else {
        console.log('💡 The MVT file has issues that need to be addressed.');
        process.exit(1);
    }
}

if (require.main === module) {
    main();
} 