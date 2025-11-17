<%*
  // Get all files in the vault
  let files = app.vault.getFiles(); // Get all files in the vault

  // Filter files that are within the 'content' directory
  let contentDir = 'content'; // Specify the directory to filter by
  let contentFiles = files.filter(f => f.path.startsWith(contentDir)); // Only include files in 'content' directory

  // Extract file paths from the filtered files
  let fileNames = contentFiles.map(f => f.path); // Extract file paths
  
  // Debug: Print all files in the 'content' directory
  //console.log("Files in 'content' directory:", fileNames);

  // Prompt the user to enter a search term
  let searchTerm = await tp.system.prompt("Search for a file (part of the filename or path)");

  // Debug: Print the search term entered by the user
  //console.log("User search term:", searchTerm);

  // Filter files based on the search term entered by the user
  let filteredFiles = fileNames.filter(file => file.toLowerCase().includes(searchTerm.toLowerCase()));

  // Debug: Print the filtered files
  //console.log("Filtered files based on search term:", filteredFiles);

  // If no matching file is found, prompt the user to try again
  if (filteredFiles.length === 0) {
    return "No matching files found. Please try a different search term.";
  }

  // Prompt the user to select a file from the filtered list
  // Ensure that we only pass the filtered files to the suggester
  let selectedFile = await tp.system.suggester(filteredFiles, filteredFiles);

  // Debug: Print the selected file path
  //console.log("User selected file:", selectedFile);

  // Check if the user has selected a valid file
  if (!selectedFile) {
    return "No valid file selected. Please try again.";
  }

  // Split the selected file path into directory and filename
  let pathParts = selectedFile.split('/');

  // Debug: Print the split path parts
  //console.log("Split file path:", pathParts);

  let dir = pathParts.slice(1, pathParts.length - 1).join('/'); // Directory part
  let filename = pathParts[pathParts.length - 1].replace('.md', ''); // Filename without .md extension

  // Debug: Print the directory and filename parts
  //console.log("Directory:", dir);
  //console.log("Filename:", filename);

  // Construct the final Markdown link
  tR = `[${filename}]({{< relref "${dir}/${filename}.md" >}})`

  // Debug: Print the final output link
  //console.log("Generated Markdown link:", tR);
%>
