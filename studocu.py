import asyncio
import aiohttp
from PIL import Image
from io import BytesIO
from tqdm.asyncio import tqdm
import sys
from typing import Tuple
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Accept": "image/avif,image/jxl,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5",
    "Accept-Language": "en-US,en;q=0.5",
    "Sec-GPC": "1",
    "Alt-Used": "doc-assets.studocu.com",
    "Sec-Fetch-Dest": "image",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "same-site",
    "Priority": "u=5, i",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}

def parse_url(original_url):
    """Parse URL to extract base pattern for background images"""
    match = re.search(r'(.*bg)\d+(\.png.*)', original_url)
    if not match:
        raise ValueError("Invalid URL format - could not find bgX.png pattern")
    return f"{match.group(1)}{{}}{match.group(2)}"


def get_input():
    """Get URL and page count from user input"""
    if len(sys.argv) == 3:
        return sys.argv[1], int(sys.argv[2])
    
    url = input("Enter document URL containing bgX.png pattern: ").strip()
    num_pages = int(input("Enter total number of pages: ").strip())
    return url, num_pages


async def download_image(session, number, base_url) -> Tuple[Image, bool]:
    # Convert number to hex without '0x' prefix and remove leading zeros
    hex_num = hex(number)[2:].lower()
    url = base_url.format(hex_num)

    try:
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                content = await response.read()
                img = Image.open(BytesIO(content))
                # Convert to RGB if necessary (PDF doesn't support RGBA)
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                return img, True
            else:
                return None, False
    except Exception as e:
        print("Exception while downloading image: ", e)
        return None, False


async def main():
    try:
        original_url, num_pages = get_input()
        base_url = parse_url(original_url)
    except ValueError as e:
        print(f"Error: {e}")
        return

    async with aiohttp.ClientSession() as session:
        tasks = []
        # Download bg1 to bg25 (1 to 37 in decimal)
        for i in range(1, num_pages + 1):
            tasks.append(download_image(session, i, base_url))

        # Wait for all downloads to complete with progress bar
        print("\nDownloading images...")
        results = await tqdm.gather(
            *tasks, desc="Progress", unit="img", file=sys.stdout, ncols=80
        )

        # Separate images and their status
        images = []
        failed_positions = []
        for i, (img, success) in enumerate(results):
            if success:
                images.append(img)
            else:
                images.append(None)
                failed_positions.append((i + 1, hex(i + 1)[2:].lower()))

        while failed_positions:
            print(f"\nFailed to download {len(failed_positions)} images:")
            for pos, hex_num in failed_positions:
                print(f"Position {pos} (bg{hex_num}.png)")

            print("\nOptions:")
            print("1. Retry downloading failed images")
            print("2. Continue with successfully downloaded images")
            print("3. Cancel entire operation")

            choice = input("\nEnter your choice (1/2/3): ").strip()

            if choice == "3":
                print("\nOperation cancelled. No PDF will be created.")
                return
            elif choice == "2":
                break
            elif choice == "1":
                # Retry failed downloads
                retry_tasks = []
                for pos, _ in failed_positions:
                    retry_tasks.append(download_image(session, pos, base_url))

                print("\nRetrying failed downloads...")
                retry_results = await tqdm.gather(
                    *retry_tasks, desc="Retrying", unit="img", file=sys.stdout, ncols=80
                )

                # Update original images list and track still-failed ones
                new_failed_positions = []
                for (pos, hex_num), (retry_img, success) in zip(
                    failed_positions, retry_results
                ):
                    if success:
                        images[pos - 1] = retry_img
                    else:
                        new_failed_positions.append((pos, hex_num))

                failed_positions = new_failed_positions
            else:
                print("\nInvalid choice. Please try again.")
                continue

        # Filter out None values (failed downloads)
        images = [img for img in images if img]

        if images:
            print("\nCreating PDF...")
            # Save the first image as PDF with the rest appended
            images[0].save(
                "output.pdf", save_all=True, append_images=images[1:], quality=95
            )
            print("PDF created successfully!")

            # Report final status
            total_pages = num_pages
            successful_pages = len(images)
            if total_pages != successful_pages:
                print(
                    f"\nWarning: Only {successful_pages} out of {total_pages} pages were successfully downloaded."
                )
        else:
            print("No images were downloaded successfully")


if __name__ == "__main__":
    asyncio.run(main())
