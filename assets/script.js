// Update time and date in top right
function updateTimeDisplay() {
    const now = new Date();

    // Format time with AM/PM
    let hours = now.getHours();
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12; // 12-hour format
    const timeString = `${String(hours).padStart(2, '0')}:${minutes}:${seconds} ${ampm}`;

    // Format date as "Sun Feb 22 2026"
    const daysOfWeek = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const dayOfWeek = daysOfWeek[now.getDay()];
    const month = months[now.getMonth()];
    const date = now.getDate();
    const year = now.getFullYear();
    const dateString = `${dayOfWeek} ${month} ${date} ${year}`;

    document.getElementById('current-time').textContent = timeString;
    document.getElementById('current-date').textContent = dateString;
}

// Update time immediately and then every second
updateTimeDisplay();
setInterval(updateTimeDisplay, 1000);

// Infinite video looping - real-time seamless loop
const bgVideo = document.getElementById('bg-video');
if (bgVideo) {
    bgVideo.addEventListener('ended', function () {
        this.currentTime = 0;
        this.play();
    }, false);

    // Real-time loop check using requestAnimationFrame for zero lag
    const loopCheckStart = 5; // Start looping from 5 seconds
    const loopThreshold = 0.1; // Check within 0.1 seconds of the end

    function checkVideoLoop() {
        if (bgVideo && !bgVideo.paused && bgVideo.currentTime >= bgVideo.duration - loopThreshold) {
            bgVideo.currentTime = loopCheckStart;
        }
        requestAnimationFrame(checkVideoLoop);
    }

    // Start the real-time loop checker
    requestAnimationFrame(checkVideoLoop);
}

const canvas = document.getElementById('Matrix');
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;
const context = canvas.getContext('2d');
const katakana = 'アァカサタナハマヤャラワガザダバパイィキシチニヒミリヰギジヂビピウゥクスツヌフムユュルグズブヅプエェケセテネヘメレヱゲゼデベペオォコソトノホモヨョロヲゴゾドボポヴッン';
const latin = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
const nums = '0123456789০১২৩৪৫৬৭৮৯';
const bangla = 'অআইঈউঊঋএঐওঔকখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহড়ঢ়য়ৎ ং ঃ ঁ';
const arabic = 'ابتثجحخدذرزسشصضطظعغفقكلمنهـوي';
const alphabet = arabic + katakana + bangla + latin + nums;
const fontSize = 22;
const columns = canvas.width / fontSize;
const rainDrops = [];
for (let x = 0; x < columns; x++) {
    rainDrops[x] = 1;
}
const draw = () => {
    context.fillStyle = 'rgba(0, 0, 0, 0.05)';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = '#0F0';
    context.font = fontSize + 'px monospace';
    for (let i = 0; i < rainDrops.length; i++) {
        const text = alphabet.charAt(Math.floor(Math.random() * alphabet.length));
        context.fillText(text, i * fontSize, rainDrops[i] * fontSize);
        if (rainDrops[i] * fontSize > canvas.height && Math.random() > 0.975) {
            rainDrops[i] = 0;
        }
        rainDrops[i]++;
    }
};
setInterval(draw, 30);