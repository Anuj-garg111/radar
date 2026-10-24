FREE SETUP — sirf GitHub (koi server/paisa nahi)

1. github.com par free account banao -> New repository -> naam: radar -> Public -> Create.
2. "uploading an existing file" par click karo. Zip unzip karke andar ki SAARI files/folders
   (collect.py, docs, .github, README.txt) drag-drop karo -> Commit changes.
   (.github dikhe nahi to folder ko directly drag karo.)
3. Settings -> Pages -> Source: Deploy from a branch -> Branch: main, Folder: /docs -> Save.
4. Settings -> Actions -> General -> Workflow permissions -> "Read and write permissions" -> Save.
5. Actions tab -> "collect" -> Run workflow. Pehli baar manual, uske baad har 30 min auto.
6. Site: https://<username>.github.io/radar/  (2-3 min lagte hain)

Optional (accuracy badhane ke liye): Settings -> Secrets and variables -> Actions -> New secret
Name: ANTHROPIC_API_KEY   Value: aapki key
