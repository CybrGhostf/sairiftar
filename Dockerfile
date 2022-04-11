RUN sudo apt update && sudo apt upgrade
RUN sudo apt install python3-pip
RUN pip3 install -U pip
RUN git clone https://github.com/CybrGhostf/sairiftar
WORKDIR /root/IftarSahur
RUN pip3 install -r requirements.txt
CMD ["python3", "iftarsahur_bot.py"]
