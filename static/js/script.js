const audioFile = document.getElementById("audioFile");
const fileName = document.getElementById("fileName");
const audioPlayer = document.getElementById("audioPlayer");
const predictButton = document.getElementById("predictButton");

const uploadUrl = predictButton.dataset.uploadUrl;

audioFile.addEventListener("change", function () {
    const file = audioFile.files[0];

    if (file) {
        fileName.textContent = file.name;

        const audioURL = URL.createObjectURL(file);
        audioPlayer.src = audioURL;
        audioPlayer.style.display = "block";

        predictButton.disabled = false;
    } else {
        fileName.textContent = "No audio selected";
        audioPlayer.src = "";
        audioPlayer.style.display = "none";
        predictButton.disabled = true;
    }
});

predictButton.addEventListener("click", async function () {
    if (audioFile.files.length === 0) {
        return;
    }

    const formData = new FormData();
    formData.append("audio", audioFile.files[0]);

    predictButton.disabled = true;
    predictButton.textContent = "Uploading...";

    try {
        const response = await fetch(uploadUrl, {
            method: "POST",
            body: formData
        });

        if (response.redirected) {
            window.location.href = response.url;
            return;
        }

        const result = await response.text();

        if (!response.ok) {
            alert(result);
            predictButton.disabled = false;
            predictButton.textContent = "Predict Genre";
            return;
        }

        alert(result);
        predictButton.disabled = false;
        predictButton.textContent = "Predict Genre";
    } catch (error) {
        alert("Upload failed.");
        predictButton.disabled = false;
        predictButton.textContent = "Predict Genre";
    }
});