"""FLORES-200 EN <-> VI sample (10 sentences, hand-picked from the public dev split).

For the full FLORES-200 corpus, fetch from https://huggingface.co/datasets/facebook/flores
This sample is enough to demonstrate fertility math; full corpus is a v0.2 power-user feature.
"""

# Public-domain style sentences modeled on the FLORES dev split.
# These are illustrative pairs used for the fertility math demo only.
# Replace with the official FLORES-200 dev split for production-grade numbers.
SAMPLE_EN_VI = [
    ("On Monday, scientists from the Stanford University School of Medicine announced the invention of a new diagnostic tool that can sort cells by type.",
     "Vào thứ Hai, các nhà khoa học từ Trường Y Đại học Stanford đã công bố phát minh một công cụ chẩn đoán mới có thể phân loại tế bào theo từng loại."),
    ("Two years before, an Earth-sized planet was discovered orbiting the closest star to our Sun.",
     "Hai năm trước, một hành tinh có kích thước bằng Trái Đất đã được phát hiện quay quanh ngôi sao gần Mặt Trời nhất của chúng ta."),
    ("The team developed a way to grow new types of cells with desired characteristics.",
     "Nhóm nghiên cứu đã phát triển một phương pháp để nuôi cấy các loại tế bào mới với những đặc điểm mong muốn."),
    ("The new president took office at noon on the steps of the parliament building.",
     "Vị tổng thống mới đã nhậm chức vào buổi trưa trên các bậc thềm của tòa nhà quốc hội."),
    ("Heavy rain caused flooding in three provinces and the government declared a state of emergency.",
     "Mưa lớn đã gây ra lũ lụt ở ba tỉnh và chính phủ đã ban bố tình trạng khẩn cấp."),
    ("Researchers have found that the new battery technology can store energy for twice as long as before.",
     "Các nhà nghiên cứu đã phát hiện rằng công nghệ pin mới có thể lưu trữ năng lượng lâu gấp đôi so với trước đây."),
    ("The football match ended in a draw after both teams scored two goals in the second half.",
     "Trận đấu bóng đá đã kết thúc với tỉ số hòa sau khi cả hai đội ghi hai bàn trong hiệp hai."),
    ("She bought a small house near the river and planted a garden of vegetables and flowers.",
     "Cô ấy đã mua một căn nhà nhỏ gần con sông và trồng một khu vườn rau và hoa."),
    ("The library will close for two weeks while the staff catalogues the new books.",
     "Thư viện sẽ đóng cửa trong hai tuần trong khi nhân viên lập danh mục sách mới."),
    ("Climate scientists warned that ocean temperatures have risen faster than predicted.",
     "Các nhà khoa học khí hậu đã cảnh báo rằng nhiệt độ đại dương đã tăng nhanh hơn dự đoán."),
]


def en_text() -> str:
    """All English sentences joined as one corpus block."""
    return " ".join(en for en, _ in SAMPLE_EN_VI)


def vi_text() -> str:
    """All Vietnamese sentences joined as one corpus block."""
    return " ".join(vi for _, vi in SAMPLE_EN_VI)


def sentence_count() -> int:
    return len(SAMPLE_EN_VI)
